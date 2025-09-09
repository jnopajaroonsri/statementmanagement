from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import BankStatement, Transaction, BankAccount, ChatBot, TransactionCategory, BankStatementParser
from .filters import TransactionFilter, StatementFilter
from .openai_test import generate_response
from . import forms #, filters
from decimal import Decimal
import google.generativeai as genai
import pdb, json, re

# Create your views here.
def pdfstatement_list(request):
    statements = BankStatement.objects.filter(bankAccount__author=request.user).order_by('-period')
    f = StatementFilter(request.GET, request=request, queryset=statements)

    paginator = Paginator(f.qs, per_page=10)
   
    page = request.GET.get('page')
    try:
        response = paginator.page(page)
    except PageNotAnInteger:
        response = paginator.page(1)
    except EmptyPage:
        response = paginator.page(paginator.num_pages)
    return render(request, 'pdfstatement/pdfstatement_list.html', { 'statements': response, 'filter_form': f })

@login_required(login_url="/users/login/")
def pdfstatement_new(request):
    if request.method == 'POST':
        form = forms.CreateStatement(request.POST, request.FILES)
        form.fields["bankAccount"].queryset = BankAccount.objects.filter(author=request.user)
        if form.is_valid():
            newpost = form.save(commit=False)
            newpost.author = request.user
            newpost.save()
            return redirect('pdfstatement:list')
    else:
        form = forms.CreateStatement()
        form.fields["bankAccount"].queryset = BankAccount.objects.filter(author=request.user)
    return render(request, 'pdfstatement/pdfstatement_new.html', { 'form': form })

def pdfstatement_view(request, slug):
    transactions = []
    statement = []
    statement = BankStatement.objects.get(slug=slug)
    transactions = Transaction.objects.filter(bankStatement=statement).order_by("postingDate")

    # descriptions only
    transactions_descriptions = transactions.values_list('description').distinct()

    return render(request, 'pdfstatement/pdfstatement_view.html', { 'statement': statement, 'transactions': transactions })

def pdfstatement_transactions_list(request):
    transactions = Transaction.objects.filter(bankStatement__bankAccount__author=request.user).order_by("postingDate")
    f = TransactionFilter(request.GET, request=request, queryset=transactions)
    paginator = Paginator(f.qs, per_page=10)
   
    page = request.GET.get('page')
    try:
        response = paginator.page(page)
    except PageNotAnInteger:
        response = paginator.page(1)
    except EmptyPage:
        response = paginator.page(paginator.num_pages)
    # context = {"page_obj": page_object}
    totalAmount = Decimal('0.0')
    pageTotalAmount = Decimal('0.0')
    for transaction in response:
        pageTotalAmount += Decimal(str(transaction.amount))
    for transaction in f.qs:
        totalAmount += Decimal(str(transaction.amount))
    return render(request, 'pdfstatement/pdfstatement_transactions_list.html', { 'totalAmount': totalAmount, 'filter': response, 'filter_form': f, 'pageTotalAmount': pageTotalAmount })

# change all transaction categories from 'a' to 'b' 
def pdfstatement_change_categories(request):
    categories = TransactionCategory.objects.filter(transaction__bankStatement__bankAccount__author=request.user).distinct().order_by("categoryName")
    transactions = Transaction.objects.filter(bankStatement__bankAccount__author=request.user, category=categories[0])

    if request.method == "POST":
        old_category = TransactionCategory.objects.get(id=int(request.POST.get('category_from')))
        new_category = TransactionCategory.objects.get(id=int(request.POST.get('category_to')))
        transactions_to_update = Transaction.objects.filter(bankStatement__bankAccount__author=request.user, category=old_category)
        transactions_to_update.update(category=new_category)
        # old way, in case update doesn't work correctly
        # for transaction in transactions_to_update:
        #     transaction.category = new_category
        #     transaction.save()
        
        # if there are no transactions using this category across the whole app, remove it
        if not Transaction.objects.filter(category=old_category):
            TransactionCategory.objects.get(id=request.POST.get('category_from')).delete()

        return render(request, 'pdfstatement/pdfstatement_transactions_list.html')
    return render(request, 'pdfstatement/pdfstatement_change_categories.html', { 'categories': categories, 'transactions': transactions})

# AJAX Functions
def load_pdfparserversions(request):
    bankAccount = BankAccount.objects.get(id=int(request.GET.get('bankAccount')))
    pdfparserversions = BankStatementParser.objects.filter(bank=bankAccount.bank).order_by("-version")
    selectedversion = pdfparserversions[0].version
    return render(request, 'pdfstatement/pdfstatement_pdfparserversion_dropdown_list_options.html', {'pdfparserversions': pdfparserversions, 'selectedversion': selectedversion})

def load_changecategoriestransactions(request):
    category = TransactionCategory.objects.get(id=request.GET.get('categoryFromId'))
    transactions_list = Transaction.objects.filter(category=category, bankStatement__bankAccount__author=request.user)
    return render(request, 'pdfstatement/pdfstatement_change_categories_transactions.html', {'transactions': transactions_list})

def pdfstatement_category_add(request):
    context = {'message': 'This is content for the popup!'}
    if request.method == "POST":
        categoryName = request.POST.get('categoryName')
        newCategory = TransactionCategory.objects.create(categoryName=categoryName)
        return render(request, 'pdfstatement/pdfstatement_transactions_list_edit.html', context)
    return render(request, 'pdfstatement/pdfstatement_category_new_popup.html', context)

# categorize based on existing categorizations, 
# and then use GeminiAI to categorize new/unencountered statement descriptions
def pdfstatement_categorize_statement_transactions(request, slug):
    transactions = []
    statement = []
    if request.method == "GET":
        statement = BankStatement.objects.get(slug=slug)
        transactions_in_statement = Transaction.objects.filter(bankStatement=statement)

        # categories for current user already in db
        category_list_from_db = Transaction.objects.filter(bankStatement__bankAccount__author=statement.bankAccount.author).exclude(category=None)
        # transactions with matching descriptions as those with categories in the db
        transactions_list_from_pdf_in_db = transactions_in_statement.filter(description__in=category_list_from_db.values_list('description', flat=True))
        # update new transactions using existing db mapping
        print("Transactions with categories in the db", flush=True)
        print(transactions_list_from_pdf_in_db, flush=True)
        if len(transactions_list_from_pdf_in_db) > 0:
            for transaction in transactions_list_from_pdf_in_db:
                print(transaction, flush=True)
                print(category_list_from_db.filter(description=transaction.description), flush=True)
                # we're iterating through single items in this list
                category = category_list_from_db.filter(description=transaction.description)
                transaction.category = category[0].category
                transaction.save()

        print("Querying Gemini for categories not in db", flush=True)
        # query AI for transactions not already categorized
        transactions_to_query_ai_list = transactions_in_statement.exclude(description__in=category_list_from_db.values_list('description', flat=True)).values_list('description', flat=True)
        print(transactions_to_query_ai_list, flush=True)
        # if list is not empty, query AI
        if len(transactions_to_query_ai_list) > 0:
            transactions_string = "\n".join(transactions_to_query_ai_list)
            ai_prompt_string = "Given the following list of credit card statement descriptions, return each description in the format 'description|category|company name':\n" + transactions_string
            print(ai_prompt_string, flush=True)

            response = chat.send_message(ai_prompt_string)
            print("AI RESPONSES:" + response.text, flush=True)
            transaction_category_mapping = {}
            for line in response.text.split("\n"):
                if re.search(r'\|', line):
                    split_line = line.split("|")

                    transaction_category_mapping[split_line[0]] = {
                        'category': split_line[1],
                        'company': split_line[2].strip()
                    }
                    continue 
            
            for transaction in transactions_to_query_ai_list:
                # if transaction description is not in the mapping returned by ai, catch and display
                if not transaction in transaction_category_mapping.keys():
                    print(transaction + " not found", flush=True)
                    continue
                else:
                    ai_response_transaction = transaction_category_mapping[transaction]
                    category = ai_response_transaction['category']
                # we shouldn't ever have to create, but this is a fallback in case of bug
                category_item, created = TransactionCategory.objects.get_or_create(categoryName=category)
                transactions_in_statement.filter(description=transaction).update(category=category_item.id)
            statement.categorizedByAI = True
            statement.save()
    return render(request, 'pdfstatement/pdfstatement_view.html', { 'statement': statement, 'transactions': transactions_in_statement })
    
@login_required
def pdfstatement_chat(request):
    # openai code
    context = {}

    if request.method == 'POST':
        user_input = request.POST.get('user_input', '')
        chat_history = request.POST.get('chat_history', '')
        prompt = f'{chat_history}\nUser: {user_input}\nChatGPT:'
        response = generate_response(prompt)
        context['chat_history'] = f'{chat_history}\nUser: {user_input}\nChatGPT: {response}'

    return render(request, 'pdfstatement/chat.html', context)

# GEMINI code
# Configure Gemini
gemini_api_key = open("pdfstatement/gemini.key").read()
genai.configure(api_key=gemini_api_key)
print("Gemini API Key:", gemini_api_key)
model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat(history=[])

@csrf_exempt
def pdfstatement_chatbot_view(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user_message = data.get("message")
        # Send message to Gemini chat
        response = chat.send_message(user_message)

        # chat bot reply
        bot_reply = response.text
        return JsonResponse({"reply": bot_reply})
    return render(request, "pdfstatement/chat_bot.html")

def add_new_option_view(request):
    if request.method == 'POST':
        new_value = request.POST.get('new_value')
        # Create and save new model instance
        # e.g., MyModel.objects.create(name=new_value)
        TransactionCategory.objects.create(categoryName=new_value)
        return JsonResponse({'status': 'success', 'message': 'Value added'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

from django.views.generic import UpdateView
from .forms import TransactionForm
class TransactionUpdateView(UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'pdfstatement/pdfstatement_transactions_list_edit.html'

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('pdfstatement:transactions-list')
    
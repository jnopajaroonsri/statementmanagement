from django import forms
from django.shortcuts import redirect
from . import models
import pdb

class CreateStatement(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # chained drop down list: 
        # https://simpleisbetterthancomplex.com/tutorial/2018/01/29/how-to-implement-dependent-or-chained-dropdown-list-with-django.html
        self.fields['pdfParserVersion'].queryset = models.BankStatementParser.objects.none()

        if 'bankAccount' in self.data:
            try:
                bankAccount_id = int(self.data.get('bankAccount'))
                bankAccount = models.BankAccount.objects.get(id=bankAccount_id)
                self.fields['pdfParserVersion'].queryset = models.BankStatementParser.objects.filter(bank__id=bankAccount.bank.id).order_by('version')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            self.fields['pdfParserVersion'].queryset = self.instance.bankAccount.bank.bankStatementParser.order_by('version')


    class Meta:
        model = models.BankStatement
        fields = ['bankAccount', 'description', 'file', 'pdfParserVersion']


class TransactionForm(forms.ModelForm):


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = self.fields['category'].queryset.order_by('categoryName')

    def save(self, commit=True):
        instance = super().save()

        if self.data.get('updateAll') == 'on':
            # call updates on other Transactions
            transaction_models_to_update = models.Transaction.objects.filter(description=instance.description, bankStatement__bankAccount__author=instance.bankStatement.bankAccount.author)
            transaction_models_to_update.update(category=instance.category)
            # old way in case update doesn't work
            # for transaction in transaction_models_to_update:
            #     transaction.category = instance.category
            #     transaction.save()

    class Meta:
        model = models.Transaction
        fields = ['category']


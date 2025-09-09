from django.db import models, transaction, IntegrityError
#from django.utils import timezone
from django.db.models import UniqueConstraint
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.urls import reverse
from uuid import uuid4
from . import pdfbofa, pdfcap1, pdfwf
import pdb, logging, datetime

# Create your models here.
class Bank(models.Model):
    bankName = models.CharField(max_length=50, null=True, blank=True)
    bankLogo = models.ImageField(default='default.png', upload_to='upload_images')
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)

    def __str__(self):
        return self.bankName
    
    def save(self, *args, **kwargs):
        if  not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[0]

        self.slug = slugify('{} {}'.format(self.bankName, self.uniqueId))
        super(Bank, self).save(*args, **kwargs)
        
class BankAccount(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, default=None)
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    description = models.TextField(null=True, blank=True)
    accountNumber = models.CharField(null=True, blank=True, max_length=30)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, default=None)

    def __str__(self):
        return '{} - {}'.format(self.bank.bankName, self.accountNumber)
    
    def save(self, *args, **kwargs):
        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[0]

        self.slug = slugify('{} {} {}'.format(self.bank.bankName, self.accountNumber, self.uniqueId))
        super(BankAccount, self).save(*args, **kwargs)

class BankStatementParser(models.Model):
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, default=None)
    version = models.CharField(blank=False, null=False)

    def __str__(self):
        return '{} - {}'.format(self.bank.bankName, self.version)
   

class BankStatement(models.Model):
    bankAccount = models.ForeignKey(BankAccount, on_delete=models.CASCADE, default=None)
    # if we implement postgres, we can leverage DateRangeField for period
    period = models.CharField(null=True, blank=True)
    periodStartDate = models.DateField(null=True, blank=True)
    periodEndDate = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    uniqueId = models.CharField(blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    file = models.FileField(null=True, unique=True, blank=False)
    amountTotal = models.DecimalField(null=True, blank=True, max_length=20, decimal_places=2, max_digits=19)
    creditTotal = models.DecimalField(null=True, blank=True, max_length=20, decimal_places=2, max_digits=19)
    debitTotal = models.DecimalField(null=True, blank=True, max_length=20, decimal_places=2, max_digits=19)
    pdfParserVersion = models.ForeignKey(BankStatementParser, on_delete=models.SET_NULL, default=None, null=True, blank=True)
    categorizedByAI = models.BooleanField(default=False)

    def __str__(self):
        return '{} - {} - {}'.format(self.bankAccount.bank.bankName, self.bankAccount.accountNumber, self.period)
    
    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)

        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[0]

        logger.debug("Bank Account::")
        logger.debug(self.bankAccount)

        # if bankStatement has not been categorizedByAI, we may still have transactions to process
        if not self.categorizedByAI:
            # extract transactions after save
            if self.bankAccount.bank.bankName == 'Bank of America':
                if self.pdfParserVersion.version == '1':
                    transactions_list, statement_range, totalBalance = pdfbofa.parsebofapdf(self.file)
            elif self.bankAccount.bank.bankName == 'Wellsfargo':
                if self.pdfParserVersion.version == '1':
                    transactions_list, statement_range, totalBalance = pdfwf.parsewfpdf(self.file)
            elif self.bankAccount.bank.bankName == 'CapitalOne':
                if self.pdfParserVersion.version == '1':
                    transactions_list, statement_range, totalBalance = pdfcap1.parsecap1pdf(self.file)

            # update period parsed from pdf    
            self.period = statement_range
            statement_start, statement_end = statement_range.split(" to ")
            self.periodStartDate = datetime.datetime.strptime(statement_start, "%Y/%m/%d")
            self.periodEndDate = datetime.datetime.strptime(statement_end, "%Y/%m/%d")
            self.amountTotal = totalBalance
            self.slug = slugify('{} {}'.format(self.period, self.uniqueId))

            # check if we're trying to reload a bankStatement for a given period for a given account
            if BankStatement.objects.filter(period=self.period, bankAccount=self.bankAccount).exists():
                self = BankStatement.objects.get(period=self.period, bankAccount=self.bankAccount)
            else:
                super(BankStatement, self).save(*args, **kwargs)

            existing_transactions = Transaction.objects.filter(transactionId__in=[d['transactionId'] for d in transactions_list], bankStatement__bankAccount=self.bankAccount).values_list('description', flat=True)
    #        logger.info(transactions_list) #update to logger
            new_transactions = []
            # update transactions_list
            for transaction_hash in transactions_list:
                transaction_hash['bankStatement'] = self
                del transaction_hash['account_number']

                # TBD:: duplicate check here
                # transaction_obj, created = Transaction.objects.get_or_create(**transaction_hash)
                if transaction_hash['description'] not in existing_transactions:
                   new_transactions.append(Transaction(**transaction_hash))
            try:
                created_objects = Transaction.objects.bulk_create(new_transactions, ignore_conflicts=True)
            except IntegrityError:
                pass
        else:
            super(BankStatement, self).save(*args, **kwargs)

class TransactionCategory(models.Model):
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    categoryName = models.CharField(null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.categoryName)
    
class Transaction(models.Model):
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    transactionDate = models.DateField(null=True, blank=True)
    postingDate = models.DateField(null=True, blank=True)
    amount = models.DecimalField(null=True, blank=True, max_length=20, decimal_places=2, max_digits=19)
    description = models.TextField(null=True, blank=True, max_length=50)
    bankStatement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, default=None)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    transactionId = models.CharField(null=False, blank=False)
    companyName= models.CharField(null=True, blank=True)
    category = models.ForeignKey(TransactionCategory, default=None, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['bankStatement', 'transactionId'], name='unique_bankStatement_transactionId')
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return '{}:{} {}'.format(self.postingDate, self.description, self.amount)
   
    def save(self, *args, **kwargs):
        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[0]

        self.slug = slugify('{} {}'.format(self.bankStatement.uniqueId, self.uniqueId))
        super(Transaction, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('pdfstatement:transactions-list')

# Gemini
class ChatBot(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="GeminiUser", null=True
    )
    text_input = models.CharField(max_length=500)
    gemini_output = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    
    def __str__(self):
        return self.text_input
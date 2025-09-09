from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Bank)
admin.site.register(BankAccount)
admin.site.register(BankStatement)
admin.site.register(Transaction)
admin.site.register(TransactionCategory)
admin.site.register(BankStatementParser)
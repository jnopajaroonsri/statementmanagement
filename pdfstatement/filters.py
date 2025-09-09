import django_filters, pdb
from django import forms
from .models import Transaction, TransactionCategory, BankStatement, BankAccount
from django.utils.translation import gettext as _

# django-filters doc
# https://django-filter.readthedocs.io/en/stable/guide/usage.html
# https://medium.com/@balt1794/chapter-15-django-filters-6947da6df52a

class TransactionFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(
        field_name='postingDate',
        lookup_expr='gte',
        label='Date From',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    end_date = django_filters.DateFilter(
        field_name='postingDate',
        lookup_expr='lte',
        label='Date To',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    description = django_filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        label='Description'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # sort Category foreign key queryset
        self.filters['category'].queryset = TransactionCategory.objects.filter(transaction__bankStatement__bankAccount__author=self.request.user).distinct().order_by('categoryName')
        self.filters['bankStatement'].queryset = BankStatement.objects.filter(bankAccount__author=self.request.user)

    class Meta:
        model = Transaction
        fields = ['category', 'bankStatement']

class StatementFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(
        field_name='periodStartDate',
        lookup_expr='gte',
        label='Start Date From',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    end_date = django_filters.DateFilter(
        field_name='periodStartDate',
        lookup_expr='lte',
        label='Start Date To',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # sort Category foreign key queryset
        self.filters['bankAccount'].queryset = BankAccount.objects.filter(author=self.request.user)

    class Meta:
        model = BankStatement
        fields = ['bankAccount']
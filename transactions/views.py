from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.views.generic import CreateView, ListView
from transactions.constants import DEPOSIT, WITHDRAWAL,LOAN, LOAN_PAID, SENDMONEY, RECIVEMONEY
from datetime import datetime
from django.db.models import Sum
from transactions.forms import (
    DepositForm,
    WithdrawForm,
    LoanRequestForm,
    sendmoneyForm,
    TransferForm,
)
from transactions.models import Transaction
from django.contrib.auth.models import User

from accounts.models import UserBankAccount
from django.shortcuts import render, redirect

# for email send
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string



class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transaction_form.html'
    model = Transaction
    title = ''
    success_url = reverse_lazy('transaction_report')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.account
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) # template e context data pass kora
        context.update({
            'title': self.title
        })

        return context



class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = 'Deposit'

    def get_initial(self):
        initial = {'transaction_type': DEPOSIT}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.account
        # if not account.initial_deposit_date:
        #     now = timezone.now()
        #     account.initial_deposit_date = now
        account.balance += amount # amount = 200, tar ager balance = 0 taka new balance = 0+200 = 200
        account.save(
            update_fields=[
                'balance'
            ]
        )

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully'
        )
        return super().form_valid(form)




class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = 'Withdraw Money'

    def get_initial(self):
        initial = {'transaction_type': WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')

        self.request.user.account.balance -= form.cleaned_data.get('amount')
        self.request.user.account.save(update_fields=['balance'])

        messages.success(
            self.request,
            f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ from your account'
        )
        
        return super().form_valid(form)

#########################################################################

class sendmoneyview(TransactionCreateMixin):
    form_class = sendmoneyForm
    title = 'Send Money'
    
    def get_initial(self):
        initial = {'transaction_type': SENDMONEY}
        return initial
    
    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        # print(amount)
        account_no = form.cleaned_data.get('account_no')
        # print(account_no)

        self.request.user.account.balance -= form.cleaned_data.get('amount')
       
        self.request.user.account.save(update_fields=['balance'])

        messages.success(
            self.request,
            f'Successfully sendmoney {"{:,.2f}".format(float(amount))}$ from your account'
        )

        return super().form_valid(form)


def transfer_money(request):
    title = 'Send Money'
    if request.method == 'POST':
        form = TransferForm(request.POST)
        if form.is_valid():
            sender_account = request.user.account  # Assuming the sender is the logged-in user
            # print(sender_account.balance)
            receiver = form.cleaned_data['receiver_account']
            print(UserBankAccount.objects.all())
            if UserBankAccount.objects.get(account_no = receiver):
                receiver_account = UserBankAccount.objects.get(account_no = receiver)
                # print(receiver_account.balance)
                amount = form.cleaned_data['amount']
                # print(amount)

                if sender_account.balance >= amount:
                    # Update sender's balance
                    sender_account.balance -= amount
                    sender_account.save()
                    # send_transaction_email(sender_account.user, amount, "send money Message", "send_money_email.html")
                    
                    
                    receiver_account.balance += amount
                    receiver_account.save()
                    # send_transaction_email(receiver_account.user, amount, "Recive money Message", "recive_money_email.html")
                    
                    
                     # Create and save a Transaction instance
                    transaction = Transaction(
                        account=sender_account,
                        amount=amount,
                        balance_after_transaction=sender_account.balance,
                        transaction_type=SENDMONEY,  # Set the actual value
                        loan_approve=False,  # You may need to set this based on your business logic
                    )
                    transaction.save()
                    transaction = Transaction(
                        account=receiver_account,
                        amount=amount,
                        balance_after_transaction=receiver_account.balance,
                        transaction_type=RECIVEMONEY,  # Set the actual value
                        loan_approve=False,  # You may need to set this based on your business logic
                    )
                    transaction.save()
                   
                    # Optionally, you can send transaction emails here

                    return redirect('home')  # Redirect to a success page
            else:
                print('User not found')
            

    else:
        form = TransferForm()
    return render(request, 'transfer_money.html', {'form': form})


class LoanRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = 'Request For Loan'

    def get_initial(self):
        initial = {'transaction_type': LOAN}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account,transaction_type=3,loan_approve=True).count()
        if current_loan_count >= 3:
            return HttpResponse("You have cross the loan limits")
        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully'
        )

        # send_transaction_email(self.request.user, amount, "Loan Request Message", "loan_email.html")
        
        return super().form_valid(form)
    
    
class TransactionReportView(LoginRequiredMixin, ListView):
    template_name = 'transaction_report.html'
    model = Transaction
    balance = 0 # filter korar pore ba age amar total balance ke show korbe
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(
            account=self.request.user.account
        )
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            queryset = queryset.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
            self.balance = Transaction.objects.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            ).aggregate(Sum('amount'))['amount__sum']
        else:
            self.balance = self.request.user.account.balance
       
        return queryset.distinct() # unique queryset hote hobe
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account': self.request.user.account
        })

        return context   
        
class PayLoanView(LoginRequiredMixin, View):
    def get(self, request, loan_id):
        loan = get_object_or_404(Transaction, id=loan_id)
        print(loan)
        if loan.loan_approve:
            user_account = loan.account
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approved = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect('loan_list')
            else:
                messages.error(
            self.request,
            f'Loan amount is greater than available balance'
        )
        return redirect('loan_list')

class LoanListView(LoginRequiredMixin,ListView):
    model = Transaction
    template_name = 'loan_request.html'
    context_object_name = 'loans'
    title = 'LOAN'
    
    def get_queryset(self):
        user_account = self.request.user.account
        queryset = Transaction.objects.filter(account=user_account,transaction_type=3)
        print(queryset)
        return queryset

from django.conf import settings

from books.models import Order
from .forms import PasswordChangeFormUser, UserCreationForm,LoginForm,VerifyForm
from django.http.response import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from .models import PreRegistration
from django.contrib.auth.models import User
from django.shortcuts import render
import random
import ssl
import certifi
from django.contrib import messages
from django.shortcuts import render,redirect
from django.core.mail import send_mail



#Create your views here.

def creatingOTP():
    otp = ""
    for i in range(5):
        otp+= f'{random.randint(0,9)}'
    return otp

def sendEmail(email, first_name, last_name, otp):
    email_message = f"""Dear {first_name} {last_name},

******* This is an automated email. Please do not reply. *******

Your One Time Password (OTP) is: {otp}

This OTP expires in 10 minutes.

If you have any queries, contact us at samikisdope07@gmail.com

Thanks & regards
BookLoop - Your Online Bookstore
Kathmandu, Nepal"""

    send_mail(
        'BookLoop — Your One Time Password',
        email_message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )




def SignUp_function(request):
    if not request.user.is_authenticated:
        if request.method == 'POST':
            form = UserCreationForm(request.POST)
            email = request.POST.get('email', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            username = request.POST.get('username', '').strip()

            if form.is_valid():
                # Check for duplicate email
                if User.objects.filter(email=email).exists():
                    messages.error(request, 'Email already taken')
                    return render(request, 'register.html', {'form': form})
                # Check for duplicate username
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already taken')
                    return render(request, 'register.html', {'form': form})

                # Generate OTP and save PreRegistration FIRST (before email)
                otp = creatingOTP()
                
                # Clear any old PreRegistration for this username/email
                PreRegistration.objects.filter(username=username).delete()
                PreRegistration.objects.filter(email=email).delete()
                
                dt = PreRegistration(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    otp=otp,
                    password1=form.cleaned_data['password1'],
                    password2=form.cleaned_data['password2'],
                )
                dt.save()
                request.session['pre_reg_id'] = dt.id

                # Try to send OTP — always redirect to /verify/ regardless of email outcome
                email_sent = False
                try:
                    sendEmail(email, first_name, last_name, otp)
                    email_sent = True
                except Exception as e:
                    print(f'[Registration] Email failed: {type(e).__name__}: {e}')

                if email_sent:
                    messages.success(request, f'OTP sent to {email}. Check your inbox (and spam folder).')
                else:
                    messages.warning(
                        request,
                        f'Could not send email automatically. Your OTP is: {otp} — '
                        f'please copy it and enter it on the next page.'
                    )

                return HttpResponseRedirect('/verify/')
            else:
                # Form has validation errors — show them clearly
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{error}')

        else:
            form = UserCreationForm()
        return render(request, 'register.html', {'form': form})
    else:
        return HttpResponseRedirect('/')




def Login_function(request):
    if request.user.is_authenticated:
        return redirect('/')
    else:
        if request.method == 'POST':
            username = request.POST.get('username')
            password =request.POST.get('password')
            # Authenticate the user using Django's built-in authentication system
            user = authenticate(request, username=username, password=password)
            # If the user credentials are valid, log them in and redirect to homepage
            if user is not None:
                login(request, user)
                return redirect('/')
            else:
                messages.info(request, 'Username OR password is incorrect')
        context = {}
        return render(request, 'login.html', context)


def logout_user(request):
    if request.method in ['GET', 'POST']:
        logout(request)
        return redirect('/')
    return redirect('/')


    
   

def verifyUser(request):
    if not request.user.is_authenticated:
        if request.method == 'POST':
            form = VerifyForm(request.POST)
            if form.is_valid():
                otp = form.cleaned_data['otp']
                pre_reg_id = request.session.get('pre_reg_id')
                if pre_reg_id:
                    data = PreRegistration.objects.filter(id=pre_reg_id, otp=otp)
                else:
                    data = PreRegistration.objects.filter(otp=otp)
                # If the OTP exists, retrieve the user details from the PreRegistration table
                if data:
                    username = ''
                    first_name = ''
                    last_name = ''
                    email = ''
                    password1 = ''
                    for i in data:
                        print(i.username)
                        username = i.username
                        first_name = i.first_name
                        last_name = i.last_name
                        email = i.email
                        password1 = i.password1
               
                    # Create a new user with the retrieved details
                    user = User.objects.create_user(username, email, password1)
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                    data.delete()
                    request.session.pop('pre_reg_id', None)
                    messages.success(request,'Account is created successfully!')
                    return HttpResponseRedirect('/login')   
                else:
                    messages.error(request,'Entered OTP is wrong')
                    return HttpResponseRedirect('/verify/')
        else:            
            form = VerifyForm()
        return render(request,'verify.html',{'form':form})
    else:
        return HttpResponseRedirect('/login')






def changePassword(request):
    if request.user.is_authenticated:
        order, created = Order.objects.get_or_create(user=request.user.username,complete=False)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
        if request.method == 'POST':
            changePasswordForm = PasswordChangeFormUser(user=request.user,data= request.POST)
            if changePasswordForm.is_valid():
                changePasswordForm.save()
                messages.success(request,"Your password is changed successfully !!")
                return HttpResponseRedirect('/login')
                
        else:
            changePasswordForm = PasswordChangeFormUser(user=request.user)
        return render(request,'chngepassword.html',{'passwordForm':changePasswordForm,'order':order,'items':items,'cartItems':cartItems})
    else:
        return HttpResponseRedirect('/store')

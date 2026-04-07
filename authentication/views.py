
from django.conf import settings

from books.models import Order
from books.forms import BookshopProductForm
from .forms import PasswordChangeFormUser, UserCreationForm, LoginForm, VerifyForm
from django.http.response import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from .models import PreRegistration, UserProfile, BookshopProfile
from django.contrib.auth.models import User
from django.shortcuts import render
import random
import ssl
import certifi
from django.contrib import messages
from django.shortcuts import render, redirect
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
                
                register_as = request.POST.get('register_as', 'student')
                if register_as not in ('student', 'bookshop'):
                    register_as = 'student'

                dt = PreRegistration(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    otp=otp,
                    password1=form.cleaned_data['password1'],
                    password2=form.cleaned_data['password2'],
                    role=register_as,
                )
                dt.save()
                request.session['pre_reg_id'] = dt.id

                # Try to send OTP — NEVER expose OTP in any HTTP response
                email_sent = False
                try:
                    sendEmail(email, first_name, last_name, otp)
                    email_sent = True
                except Exception as e:
                    print(f'[Registration] Email failed: {type(e).__name__}: {e}')

                if email_sent:
                    messages.success(
                        request,
                        f'A verification code has been sent to {email}. '
                        f'Please check your inbox and spam folder.'
                    )
                else:
                    # Log OTP server-side only — never surface it to the browser
                    print(f'[Registration] OTP for {username} ({email}): {otp}')
                    messages.error(
                        request,
                        f'We could not send a verification email to {email}. '
                        f'Please check your email address is correct and try registering again. '
                        f'If the problem persists, contact support at samikisdope07@gmail.com'
                    )
                    # Clean up so the user can re-register without "already taken" errors
                    PreRegistration.objects.filter(id=dt.id).delete()
                    request.session.pop('pre_reg_id', None)
                    return render(request, 'register.html', {'form': form})

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

                    # Capture role before deleting PreRegistration
                    role = 'student'
                    for item in data:
                        role = getattr(item, 'role', 'student')

                    # Create UserProfile
                    UserProfile.objects.create(user=user, role=role)

                    # If bookshop, create an empty BookshopProfile
                    if role == 'bookshop':
                        BookshopProfile.objects.create(
                            user=user,
                            shop_name=f"{user.first_name}'s Bookshop",
                            location='',
                        )

                    data.delete()
                    request.session.pop('pre_reg_id', None)
                    messages.success(request, 'Account created successfully! Please log in.')
                    return HttpResponseRedirect('/login')   
                else:
                    messages.error(request,'Entered OTP is wrong')
                    return HttpResponseRedirect('/verify/')
        else:            
            form = VerifyForm()
        return render(request,'verify.html',{'form':form})
    else:
        return HttpResponseRedirect('/login')






from django.contrib.auth.decorators import login_required
from books.models import Product


@login_required
def bookshop_dashboard(request):
    """Bookshop owner dashboard — manage their shop and submitted books."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found.')
        return redirect('/')

    if not profile.is_bookshop_owner:
        messages.error(request, 'This page is only for bookshop owners.')
        return redirect('/')

    try:
        bookshop = request.user.bookshop
    except BookshopProfile.DoesNotExist:
        bookshop = BookshopProfile.objects.create(
            user=request.user,
            shop_name=f"{request.user.first_name}'s Bookshop",
            location='',
        )

    my_books = Product.objects.filter(seller=request.user).order_by('-pub_date')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_shop':
            bookshop.shop_name   = request.POST.get('shop_name', bookshop.shop_name).strip()
            bookshop.location    = request.POST.get('location', bookshop.location).strip()
            bookshop.phone       = request.POST.get('phone', bookshop.phone).strip()
            bookshop.description = request.POST.get('description', bookshop.description).strip()
            bookshop.save()
            messages.success(request, 'Shop details updated successfully!')
            return redirect('bookshop_dashboard')

    return render(request, 'bookshop_dashboard.html', {
        'bookshop': bookshop,
        'my_books': my_books,
        'pending_count':  my_books.filter(listing_status='pending').count(),
        'approved_count': my_books.filter(listing_status='approved').count(),
        'rejected_count': my_books.filter(listing_status='rejected').count(),
    })


@login_required
def bookshop_add_book(request):
    """Bookshop owner submits a book listing.

    Verified shops go live immediately (listing_status='approved').
    Unverified shops are queued for admin review (listing_status='pending').
    """
    try:
        profile = request.user.profile
        if not profile.is_bookshop_owner:
            messages.error(request, 'Only bookshop owners can add books.')
            return redirect('/')
    except UserProfile.DoesNotExist:
        return redirect('/')

    try:
        bookshop = request.user.bookshop
    except BookshopProfile.DoesNotExist:
        messages.error(request, 'Bookshop profile not found.')
        return redirect('bookshop_dashboard')

    if request.method == 'POST':
        form = BookshopProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller       = request.user
            product.listing_type = 'sell'
            # Verified shops go live immediately; others wait for admin review
            product.listing_status = 'approved' if bookshop.is_verified else 'pending'
            product.save()

            if product.listing_status == 'approved':
                messages.success(
                    request,
                    f'"{product.Book_name}" is now live in the store!'
                )
            else:
                messages.info(
                    request,
                    f'"{product.Book_name}" submitted for review. '
                    f'Your shop is not yet verified — an admin will approve it shortly. '
                    f'Ask an admin to verify your shop for instant publishing.'
                )
            return redirect('bookshop_dashboard')
        # Surface form errors as messages
        for field, errs in form.errors.items():
            label = form.fields[field].label if field in form.fields else field
            for err in errs:
                messages.error(request, f'{label}: {err}')
    else:
        form = BookshopProductForm()

    return render(request, 'bookshop_add_book.html', {
        'form': form,
        'bookshop': bookshop,
    })


def changePassword(request):
    if request.user.is_authenticated:
        order, created = Order.objects.get_or_create(user=request.user.username, complete=False)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
        if request.method == 'POST':
            changePasswordForm = PasswordChangeFormUser(user=request.user, data=request.POST)
            if changePasswordForm.is_valid():
                changePasswordForm.save()
                messages.success(request, "Your password is changed successfully !!")
                return HttpResponseRedirect('/login')
        else:
            changePasswordForm = PasswordChangeFormUser(user=request.user)
        return render(request, 'chngepassword.html', {
            'passwordForm': changePasswordForm,
            'order': order,
            'items': items,
            'cartItems': cartItems,
        })
    else:
        return HttpResponseRedirect('/store')

from django import forms
from django.contrib.auth.models import User
from django.forms import fields
from django.contrib.auth.forms import UserCreationForm,AuthenticationForm, UsernameField, PasswordChangeForm
from django.core import validators


def validate_username(value):
# Check if the length of the username is less than or equal to 2
    if len(value)<=2: 
        raise forms.ValidationError(f"Your username cannot be of {len(value)}  word")



class UserCreationForm(UserCreationForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"First Name","required":True}),error_messages={"required":"First name cannot be empty"})
    last_name = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Last Name","required":True}),error_messages={"required":"Last name cannot be empty"})
    username = forms.CharField(label="Username",widget=forms.TextInput(attrs={"placeholder":"Username","id":"username"}),validators=[validate_username],error_messages={'required':'Username is required'})
    email = forms.CharField(widget=forms.EmailInput(attrs={"required":True,"Placeholder":"Email",'autocomplete':'username'}),error_messages={'required':'Email field cannot be empty'})
    password1 = forms.CharField(label="Password", widget = forms.PasswordInput(attrs={"placeholder":"Password",'autocomplete':'new-password'}),error_messages={"required":"Please enter password"})
    password2 = forms.CharField(label="Confirm Password",widget= forms.PasswordInput(attrs={"placeholder":"Re-enter Password",'autocomplete':'new-password'}),help_text="Make sure your password contains 'Letters','Numbers' and 'Symbols'",error_messages={"required":"Please Re-Enter the password"})
    class  Meta:
         model = User
         fields = ['first_name', 'last_name', 'username', 'email']
   
class VerifyForm(forms.Form):
    otp = forms.CharField(label='OTP',max_length=70,widget=forms.TextInput(attrs={'class':'form-control','placeholder':'OTP','required':True}),error_messages={'required':'Please Enter the OTP'})



class LoginForm(AuthenticationForm):
    username = UsernameField(widget=forms.TextInput(attrs={"placeholder":"Username",'class':'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder":"password",'autocomplete':'current-password','class':'form-control'}))    
    

class PasswordChangeFormUser(PasswordChangeForm):
    old_password = forms.CharField(label=("Password"),strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'new-password','class':'class','placeholder':'old password'}))
    new_password1 =forms.CharField(label=("Password"),strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'new-password','class':'class','placeholder':'new password'})) 
    new_password2 =forms.CharField(label=("Password"),strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'new-password','class':'class','placeholder':'confirm password'})) 
    

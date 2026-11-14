"""Users, roles, and department scope."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.accounts.forms import AccountPasswordChangeForm, LoginForm, ProfileForm


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy("accounts:login")


@login_required
def profile(request):
    """Show account details and let the user edit only personal fields."""
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            # Explicit fields keep authorization data out of this write.
            user.save(update_fields=["ho_ten", "email"])
            messages.success(request, "Đã cập nhật thông tin tài khoản.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})


class AccountSettingsView(PasswordChangeView):
    """The account setting available today: changing the password."""

    template_name = "accounts/settings.html"
    form_class = AccountPasswordChangeForm
    success_url = reverse_lazy("accounts:settings")

    def form_valid(self, form):
        messages.success(self.request, "Đã đổi mật khẩu.")
        return super().form_valid(form)

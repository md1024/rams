from common import *

def randstring():
    return "".join(chr(randrange(33,127)) for i in range(8))

def valid_password(password, account):
    all_hashed = [account.hashed] + list(account.passwordreset_set.values_list("hashed", flat=True))
    return any(bcrypt.hashpw(password, hashed) == hashed for hashed in all_hashed)

@all_renderable(ACCOUNTS)
class Root:
    @unrestricted
    def login(self, message="", **params):
        if "email" in params:
            try:
                account = Account.objects.get(email__iexact=params["email"])
                PasswordReset.objects.filter(generated__lt = datetime.now() - timedelta(days=7)).delete()
                if not valid_password(params["password"], account):
                    message = "Incorrect password"
            except:
                message = "No account exists for that email address"
            
            if not message:
                cherrypy.session["account_id"] = account.id
                raise HTTPRedirect("homepage")
        
        return {
            "message": message,
            "email":   params.get("email", "")
        }
    
    @unrestricted
    def homepage(self, message=""):
        if not cherrypy.session.get("account_id"):
            raise HTTPRedirect("login?message={}", "You are not logged in")
        return {"message": message}
    
    @unrestricted
    def logout(self):
        cherrypy.session["account_id"] = None
        raise HTTPRedirect("login?message={}", "You have been logged out")
    
    @unrestricted
    def reset(self, message="", email=None):
        if email is not None:
            account = Account.objects.filter(email=email)
            if not account:
                message = "No account exists for email address {!r}".format(email)
            else:
                account = account[0]
                password = randstring()
                PasswordReset.objects.create(account=account, hashed=bcrypt.hashpw(password, bcrypt.gensalt()))
                data = {
                    "name": account.name,
                    "password":  password
                }
                send_email(ADMIN_EMAIL, account.email, "MAGFest Admin Password Reset",
                           render("accounts/reset_email.txt", data))
                raise HTTPRedirect("login?message={}", "Your new password has been emailed to you")
        
        return {
            "email":   email,
            "message": message
        }
    
    @unrestricted
    def change_password(self, message="", old_password=None, new_password=None):
        if not cherrypy.session.get("account_id"):
            raise HTTPRedirect("login?message={}", "You are not logged in")
        
        if old_password is not None:
            account = Account.objects.get(id = cherrypy.session["account_id"])
            if not valid_password(old_password, account):
                message = "Incorrect old password; please try again"
            else:
                account.hashed = bcrypt.hashpw(new_password, bcrypt.gensalt())
                account.save()
                raise HTTPRedirect("homepage?message={}", "Your password has been updated")
        
        return {"message": message}
    
    def index(self, message="", order="name"):
        return {
            "message":  message,
            "order":    Order(order),
            "accounts": Account.objects.order_by(order)
        }
    
    def feed(self, page = "1"):
        page = int(page)
        return {
            "page": page,
            "count": Tracking.objects.count(),
            "feed": get_page(page, Tracking.objects.order_by("-id"))
        }
    
    def update(self, password="", **params):
        account = get_model(Account, params, checkgroups=["access"])
        is_new = account.id is None
        if is_new:
            if state.AT_THE_CON:
                account.hashed = bcrypt.hashpw(password, bcrypt.gensalt())
            else:
                password = randstring()
                account.hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        
        message = check(account)
        if not message:
            account.save()
            message = "Account settings uploaded"
            if is_new and not state.AT_THE_CON:
                data = {
                    "account": account,
                    "password": password
                }
                send_email(ADMIN_EMAIL, account.email, "New MAGFest Ubersystem Account",
                           render("accounts/new_email.txt", data))
        
        raise HTTPRedirect("index?message={}", message)
    
    def delete(self, id):
        Account.objects.filter(id=id).delete()
        raise HTTPRedirect("index?message={}", "Account deleted")
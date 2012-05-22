from common import *

@property
def payment_deadline(self):
    return datetime.combine((self.registered + timedelta(days = 14)).date(), time(11, 59))

def __repr__(self):
    display = getattr(self, "display", "name" if hasattr(self, "name") else "id")
    return "<{}>".format(" ".join(str(getattr(self, field)) for field in listify(display)))

class MagModelMeta(base.ModelBase):
    def __new__(cls, name, bases, attrs):
        attrs["Meta"] = type("Meta", (), {"app_label": "", "db_table": name})
        attrs["__repr__"] = __repr__
        if name in ["Group", "Attendee"]:
            attrs["payment_deadline"] = payment_deadline
        return base.ModelBase.__new__(cls, name, (Model,), attrs)

MagModel = type.__new__(MagModelMeta, "MagModel", (), {})


class Account(MagModel):
    name   = CharField(max_length = 50)
    email  = CharField(max_length = 50)
    hashed = CharField(max_length = 128)
    access = CommaSeparatedIntegerField(max_length = 50)
    
    @staticmethod
    def access_set(id=None):
        try:
            id = id or cherrypy.session.get("account_id")
            return set(int(a) for a in Account.objects.get(id=id).access.split(","))
        except:
            return set()

class PasswordReset(MagModel):
    account   = ForeignKey(Account)
    generated = DateTimeField(auto_now_add = True)
    hashed    = CharField(max_length = 128)



class MoneySource(MagModel):
    name = CharField(max_length = 50)

class MoneyDept(MagModel):
    name = CharField(max_length = 50)
    amount = IntegerField()
    
    @property
    def allocations(self):
        return self.money_set.order_by("-amount", "name")
    
    @property
    def allocated(self):
        return sum(m.amount for m in self.allocations)

class Money(MagModel):
    type        = IntegerField(choices = BUDGET_TYPE_OPTS)
    name        = CharField(max_length = 50)
    amount      = IntegerField()
    description = TextField()
    paid_by     = ForeignKey(MoneySource, null = True)
    dept        = ForeignKey(MoneyDept, null = True)
    pledged     = BooleanField()
    estimate    = BooleanField()
    pre_con     = BooleanField()
    
    @cached_property
    def payment_total(self):
        return sum(p.amount for p in self.payment_set.all())

class Payment(MagModel):
    money  = ForeignKey(Money)
    type   = IntegerField(choices = PAYMENT_TYPE_OPTS)
    amount = IntegerField()
    name   = CharField(max_length = 50)
    day    = DateField()





class Event(MagModel):
    location    = IntegerField(choices=EVENT_LOC_OPTS)
    start_time  = DateTimeField()
    duration    = IntegerField()
    name        = CharField(max_length = 99)
    description = TextField()
    
    @property
    def half_hours(self):
        half_hours = set()
        for i in range(self.duration):
            half_hours.add(self.start_time + timedelta(minutes = 30 * i))
        return half_hours



class Group(MagModel):
    name        = CharField(max_length = 50)
    tables      = IntegerField()
    amount_paid = IntegerField(default = 0)
    amount_owed = IntegerField(default = 0)
    approved    = BooleanField(default = True)
    auto_recalc = BooleanField(default = True)
    can_add     = BooleanField(default = False)
    admin_notes = TextField()
    registered  = DateTimeField(auto_now_add = True)
    
    restricted = ["amount_paid","amount_owed","auto_recalc","admin_notes","lockable"]
    
    def save(self, *args, **kwargs):
        if self.auto_recalc:
            self.amount_owed = self.total_cost
        super(Group, self).save(*args, **kwargs)
    
    @cached_property
    def email(self):
        return self.leader.email
    
    @cached_property
    def leader(self):
        for a in self.attendee_set.order_by("id"):
            if a.email:
                break
        return a
    
    @property
    def badges_purchased(self):
        return self.attendee_set.filter(paid = PAID_BY_GROUP).count()
    
    @property
    def badges(self):
        return self.attendee_set.count()
    
    @property
    def unregistered_badges(self):
        return self.attendee_set.filter(first_name = "").count()
    
    @property
    def table_cost(self):
        return (125 + 200 * (self.tables - 1)) if self.tables else 0
    
    @property
    def badge_cost(self):
        total = 0
        for attendee in self.attendee_set.filter(paid = PAID_BY_GROUP):
            if attendee.ribbon == DEALER_RIBBON:
                total += DEALER_BADGE_PRICE
            elif attendee.registered <= state.PRICE_BUMP:
                total += EARLY_GROUP_PRICE
            else:
                total += LATE_GROUP_PRICE
        return total
    
    @property
    def total_cost(self):
        return self.table_cost + self.badge_cost
    
    @property
    def amount_unpaid(self):
        return self.amount_owed - self.amount_paid



class Attendee(MagModel):
    group         = ForeignKey(Group, null = True)
    placeholder   = BooleanField(default = False)
    first_name    = CharField(max_length = 25)
    last_name     = CharField(max_length = 25)
    international = BooleanField(default = False)
    zip_code      = CharField(max_length = 20)
    ec_phone      = CharField(max_length = 20)
    phone         = CharField(max_length = 20)
    email         = CharField(max_length = 50)
    age_group     = IntegerField(default = AGE_UNKNOWN, choices = AGE_GROUP_OPTS)
    
    interests   = CommaSeparatedIntegerField(max_length = 50)
    found_how   = CharField(max_length = 100)
    comments    = CharField(max_length = 255)
    admin_notes = TextField()
    
    badge_num  = IntegerField(default = 0)
    badge_type = IntegerField(choices = BADGE_OPTS)
    ribbon     = IntegerField(default = NO_RIBBON, choices = RIBBON_OPTS)
    
    affiliate    = CharField(max_length = 50, default = "")
    can_spam     = BooleanField(default = False)
    regdesk_info = CharField(max_length = 255, default = "")
    extra_merch  = CharField(max_length = 255, default = "")
    got_merch    = BooleanField(default = False)
    
    registered = DateTimeField(auto_now_add = True)
    checked_in = DateTimeField(null = True)
    
    paid            = IntegerField(default = NOT_PAID, choices = PAID_OPTS)
    amount_paid     = IntegerField(default = 0)
    amount_refunded = IntegerField(default = 0)
    
    badge_printed_name = CharField(max_length = 30, default = "")
    
    staffing        = BooleanField(default = False)
    requested_depts = CommaSeparatedIntegerField(max_length = 50)
    assigned_depts  = CommaSeparatedIntegerField(max_length = 50)
    trusted         = BooleanField(default = False)
    nonshift_hours  = IntegerField(default = 0)
    
    display = "full_name"
    restricted = ["group","admin_notes","badge_num","ribbon","regdesk_info","extra_merch","got_merch","paid","amount_paid","amount_refunded","assigned_depts","trusted","nonshift_hours"]
    
    def save(self, *args, **kwargs):
        import badge_funcs
        
        if self.ribbon == DEPT_HEAD_RIBBON:
            self.badge_type = STAFF_BADGE
            self.staffing = self.trusted = True
            if self.paid == NOT_PAID:
                self.paid = NEED_NOT_PAY
        
        with BADGE_LOCK:
            if not state.AT_THE_CON:
                if self.paid == NOT_PAID:
                    self.badge_num = 0
                elif not self.badge_num and self.badge_type in PREASSIGNED_BADGE_TYPES:
                    self.badge_num = badge_funcs.next_badge_num(self.badge_type)
        
        if self.badge_type != SUPPORTER_BADGE:
            self.affiliate = ""
        
        if self.staffing and self.badge_type == ATTENDEE_BADGE and self.ribbon == NO_RIBBON:
            self.ribbon = VOLUNTEER_RIBBON
        
        if self.badge_type == STAFF_BADGE or self.ribbon == VOLUNTEER_RIBBON:
            self.staffing = True
        elif self.age_group == UNDER_18:
            self.staffing = False
        
        if not self.staffing:
            self.requested_depts = self.assigned_depts = ""
        
        if self.paid == NEED_NOT_PAY:
            self.amount_paid = 0
        
        if self.paid != REFUNDED:
            self.amount_refunded = 0
        
        if state.AT_THE_CON and self.badge_num and self.id is None:
            self.checked_in = datetime.now()
        
        for attr in ["first_name", "last_name"]:
            value = getattr(self, attr)
            if value.isupper() or value.islower():
                setattr(self, attr, value.title())
        
        super(Attendee, self).save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        import badge_funcs
        with BADGE_LOCK:
            badge_num = Attendee.objects.get(id = self.id).badge_num
            super(Attendee, self).delete(*args, **kwargs)
            badge_funcs.shift_badges(self.badge_type, badge_num, down=True)
    
    @classmethod
    def staffers(cls):
        return cls.objects.filter(staffing = True).order_by("first_name","last_name")
    
    @property
    def total_cost(self):
        if self.badge_type == SUPPORTER_BADGE:
            return SUPPORTER_BADGE_PRICE
        elif self.badge_type == ONE_DAY_BADGE:
            return ONEDAY_BADGE_PRICE
        elif self.registered < state.PRICE_BUMP:
            return EARLY_BADGE_PRICE
        elif self.registered < state.EPOCH:
            return LATE_BADGE_PRICE
        else:
            return DOOR_BADGE_PRICE
    
    @property
    def is_unassigned(self):
        return not self.first_name
    
    @property
    def is_dealer(self):
        return self.ribbon == DEALER_RIBBON
    
    @property
    def full_name(self):
        if self.group and self.is_unassigned:
            return "[Unassigned {self.badge}]".format(self = self)
        else:
            return "{self.first_name} {self.last_name}".format(self = self)
    
    @property
    def last_first(self):
        if self.group and self.is_unassigned:
            return "[Unassigned {self.badge}]".format(self = self)
        else:
            return "{self.last_name}, {self.first_name}".format(self = self)
    
    @property
    def badge(self):
        if self.paid == NOT_PAID:
            badge = "Unpaid " + self.get_badge_type_display()
        elif self.badge_num:
            badge = "{} #{}".format(self.get_badge_type_display(), self.badge_num)
        else:
            badge = self.get_badge_type_display()
        
        if self.ribbon != NO_RIBBON:
            badge += " ({})".format(self.get_ribbon_display())
        
        return badge
    
    def comma_and(self, xs):
        if len(xs) > 1:
            xs[-1] = "and " + xs[-1]
        return (", " if len(xs) > 2 else " ").join(xs)
    
    @property
    def merch(self):
        merch = []
        if self.badge_type == SUPPORTER_BADGE:
            merch.extend(["a tshirt", "a supporter pack", "a $10 M-Point coin"])
        if self.extra_merch:
            stuff.append(self.extra_merch)
        return self.comma_and(merch)
    
    @property
    def accoutrements(self):
        stuff = [] if self.ribbon == NO_RIBBON else ["a " + self.get_ribbon_display() + " ribbon"]
        stuff.append("a {} wristband".format(WRISTBAND_COLORS[self.age_group]))
        if self.regdesk_info:
            stuff.append(self.regdesk_info)
        return self.comma_and(stuff)
    
    @property
    def multiply_assigned(self):
        return "," in self.assigned
    
    @property
    def takes_shifts(self):
        return (self.staffing and not self.placeholder
                              and self.ribbon != DEPT_HEAD_RIBBON
                              and set(self.assigned) - {CONCERT, MARKETPLACE})
    
    @property
    def assigned(self):
        return map(int, self.assigned_depts.split(",")) if self.assigned_depts else []
    
    @property
    def assigned_display(self):
        return [dict(JOB_LOC_OPTS)[loc] for loc in self.assigned]
    
    @property
    def signups(self):
        return self.shift_set.select_related().order_by("job__start_time")
    
    @cached_property
    def hours(self):
        all_hours = set()
        for shift in self.shift_set.select_related():
            all_hours.update(shift.job.hours)
        return all_hours
    
    @cached_property
    def hour_map(self):
        all_hours = {}
        for shift in self.shift_set.select_related():
            for hour in shift.job.hours:
                all_hours[hour] = shift.job
        return all_hours
    
    # TODO: make this efficient
    @cached_property
    def possible(self):
        if not self.assigned:
            return []
        else:
            return [job for job in Job.objects.filter(location__in = self.assigned).order_by("start_time")
                        if job.slots > job.shift_set.count()
                           and job.no_overlap(self)
                           and (not job.restricted or self.trusted)]
    
    @property
    def possible_opts(self):
        return [(job.id,"%s (%s)" % (job.name, hour_day_format(job.start_time))) for job in self.possible]
    
    @property
    def possible_and_current(self):
        all = [s.job for s in self.signups]
        for job in all:
            job.already_signed_up = True
        all.extend(self.possible)
        return sorted(all, key=lambda j: j.start_time)
    
    @cached_property
    def shifts(self):
        return list(self.shift_set.select_related())
    
    @cached_property
    def worked_shifts(self):
        return list(self.shift_set.filter(worked=SHIFT_WORKED).select_related())
    
    @cached_property
    def weighted_hours(self):
        wh = sum((shift.job.real_duration * shift.job.weight for shift in self.shifts), 0.0)
        return wh + self.nonshift_hours
    
    @cached_property
    def worked_hours(self):
        wh = sum((shift.job.real_duration * shift.job.weight for shift in self.worked_shifts), 0.0)
        return wh + self.nonshift_hours


class Job(MagModel):
    event       = ForeignKey(Event, null = True)
    name        = CharField(max_length = 100)
    description = CharField(max_length = 100)
    location    = IntegerField(choices = JOB_LOC_OPTS)
    start_time  = DateTimeField()
    duration    = IntegerField()
    weight      = FloatField()
    slots       = IntegerField()
    restricted  = BooleanField(default = False)
    extra15     = BooleanField(default = False)
    
    @property
    def hours(self):
        hours = set()
        for i in range(self.duration):
            hours.add(self.start_time + timedelta(hours=i))
        return hours
    
    def no_overlap(self, attendee):
        before = self.start_time - timedelta(hours=1)
        after  = self.start_time + timedelta(hours=self.duration)
        return (not self.hours.intersection(attendee.hours)
            and (before not in attendee.hour_map
                or not attendee.hour_map[before].extra15
                or self.location == attendee.hour_map[before].location)
            and (after not in attendee.hour_map
                or not self.extra15
                or self.location == attendee.hour_map[after].location))
    
    # TODO: make this efficient
    @cached_property
    def available_staffers(self):
        return [s for s in Attendee.objects.order_by("last_name","first_name")
                if self.location in s.assigned
                   and self.no_overlap(s)
                   and (s.trusted or not self.restricted)]
        
    @property
    def real_duration(self):
        return self.duration + (0.25 if self.extra15 else 0)
    
    @property
    def weighted_hours(self):
        return self.weight * self.real_duration

class Shift(MagModel):
    job      = ForeignKey(Job)
    attendee = ForeignKey(Attendee)
    worked   = IntegerField(choices = WORKED_OPTS, default = SHIFT_UNMARKED)



class Challenge(MagModel):
    game   = CharField(max_length = 100)
    normal = BooleanField()
    hard   = BooleanField()
    expert = BooleanField()
    unfair = BooleanField()
    
    display = "game"
    
    def has_level(self, level):
        return {NORMAL:self.normal, HARD:self.hard, EXPERT:self.expert, UNFAIR:self.unfair}[int(level)]

class Success(MagModel):
    challenge = ForeignKey(Challenge)
    attendee  = ForeignKey(Attendee)
    level     = IntegerField(choices = LEVEL_OPTS)





class MPointUse(MagModel):
    attendee = ForeignKey(Attendee)
    amount   = IntegerField()
    when     = DateTimeField(auto_now_add = True)

class MPointExchange(MagModel):
    attendee = ForeignKey(Attendee)
    mpoints  = IntegerField()
    when     = DateTimeField(auto_now_add = True)

class Sale(MagModel):
    what    = CharField(max_length = 50)
    cash    = IntegerField()
    mpoints = IntegerField()
    when    = DateTimeField(auto_now_add = True)



class Email(MagModel):
    fk_id   = IntegerField()
    fk_tab  = CharField(max_length = 50)
    subject = CharField(max_length = 255)
    dest    = CharField(max_length = 100)
    when    = DateTimeField(auto_now_add = True)
    body    = TextField()
    
    display = "subject"
    
    @cached_property
    def fk(self):
        return globals()[self.fk_tab].objects.get(id = self.fk_id)
    
    @property
    def rcpt_name(self):
        if self.fk_tab == "Group":
            return self.fk.leader.full_name
        else:
            return self.fk.full_name
    
    count = 0   # TODO: replace this with something more efficient


class Tracking(MagModel):
    when   = DateTimeField(auto_now_add = True)
    who    = CharField(max_length = 50)
    which  = CharField(max_length = 50)
    model  = CharField(max_length = 50)
    fk_id  = IntegerField()
    action = IntegerField(choices = TRACKING_OPTS)
    data   = TextField()
    
    @classmethod
    def repr(self, x):
        s = repr(x)
        if isinstance(x, long):
            return s[:-1]
        elif isinstance(x, unicode):
            return s[1:]
        else:
            return s
    
    @classmethod
    def values(cls, instance):
        return {field.name: getattr(instance, field.name) for field in instance._meta.fields}
    
    @classmethod
    def format(cls, values):
        return ", ".join("{}={}".format(k, cls.repr(v)) for k,v in values.items())
    
    @classmethod
    def track(cls, action, instance):
        if action == CREATED:
            data = cls.format(cls.values(instance))
        elif action == UPDATED:
            curr = cls.values(instance)
            orig = cls.values(instance.__class__.objects.get(id = instance.id))
            diff = {name: "{} -> {}".format(cls.repr(orig[name]), cls.repr(val))
                    for name,val in curr.items() if val != orig[name]}
            data = cls.format(diff)
            if not data:
                return
        else:
            data = ""
        
        try:
            who = Account.objects.get(id = cherrypy.session.get("account_id")).name
        except:
            who = current_thread().name if current_thread().daemon else "non-admin"
        
        return Tracking.objects.create(
            model = instance.__class__.__name__,
            which = repr(instance),
            who = who,
            fk_id = instance.id,
            action = action,
            data = data,
        )

@receiver(pre_save)
def update_hook(sender, instance, **kwargs):
    if instance.id is not None and sender is not Tracking:
        Tracking.track(UPDATED, instance)

@receiver(post_save)
def create_hook(sender, instance, created, **kwargs):
    if created and sender is not Tracking:
        Tracking.track(CREATED, instance)

@receiver(pre_delete)
def delete_hook(sender, instance, **kwargs):
    if sender is not Tracking:
        Tracking.track(DELETED, instance)
from common import *
import models

from sys import argv
from django.db import connection

classes = [m for m in models.__dict__.values() if isinstance(m, models.MagModelMeta) and m is not models.MagModel]

class Style:
    def __getattr__(self, name):
        return lambda text: text

if len(argv) > 1:
    classes = [c for c in classes if c.__name__ in argv[1:]]

text = open("models.py").read()
classes.sort(key = lambda c: text.index("class " + c.__name__))

if __name__ == "__main__":
    for model in reversed(classes):
        print("DROP TABLE IF EXISTS `{}`;".format(model.__name__))
    
    print("")
    for model in classes:
        print(connection.creation.sql_create_model(model, Style(), classes)[0][0])

"""
Account.objects.create(name   = "Eli Courtwright",
                       email  = "eli@courtwright.org",
                       access = ",".join(str(level) for level,name in ACCESS_OPTS),
                       hashed = "$2a$12$RznxTw/KKp3UkGNJy0cas.hUbM4Dai3sokxo/QeAvS42QqLN56tW6")

MoneySource.objects.create(name="MAGFest funds")
MoneyDept.objects.create(name="Refunds", amount=2000)
"""
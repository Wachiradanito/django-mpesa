"""
Concrete model subclasses used by the test suite.

These subclass the abstract models from django_mpesa.models and add no
extra fields. They exist solely so the library's own tests have a real
concrete model to work with.

Host apps add their own domain fields (order, user, wallet) on their
own concrete subclass — these test models stay minimal.
"""

from django_mpesa.models import AbstractMpesaCallbackLog, AbstractMpesaTransaction


class MpesaTransaction(AbstractMpesaTransaction):
    class Meta(AbstractMpesaTransaction.Meta):
        app_label = "testapp"


class MpesaCallbackLog(AbstractMpesaCallbackLog):
    class Meta(AbstractMpesaCallbackLog.Meta):
        app_label = "testapp"

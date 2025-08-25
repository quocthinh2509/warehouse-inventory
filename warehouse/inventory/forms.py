from django import forms
from .models import Product, Warehouse

class GenerateForm(forms.Form):
    sku  = forms.CharField(max_length=64)
    name = forms.CharField(max_length=255)
    qty  = forms.IntegerField(min_value=1, max_value=5000, initial=10)
    mark_in = forms.BooleanField(initial=True, required=False)
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # đảm bảo dropdown luôn có dữ liệu mới nhất
        self.fields["warehouse"].queryset = Warehouse.objects.all()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mark_in") and not cleaned.get("warehouse"):
            raise forms.ValidationError("Bạn bật 'Ghi nhận nhập kho' nhưng chưa chọn kho.")
        return cleaned

class ScanMoveForm(forms.Form):
    ACTIONS = (("IN","IN"),("OUT","OUT"),("TRANSFER","TRANSFER"))
    action = forms.ChoiceField(choices=ACTIONS)
    barcode = forms.CharField(
        max_length=128,
        widget=forms.TextInput(attrs={"placeholder":"VD: NX-100ML-000123", "autofocus":"autofocus"})
    )
    from_wh = forms.ModelChoiceField(queryset=Warehouse.objects.all(), required=False)
    to_wh   = forms.ModelChoiceField(queryset=Warehouse.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # luôn load danh sách kho mới nhất
        self.fields["from_wh"].queryset = Warehouse.objects.all()
        self.fields["to_wh"].queryset = Warehouse.objects.all()

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        if action == "IN" and not cleaned.get("to_wh"):
            raise forms.ValidationError("IN cần chọn 'To kho'.")
        if action == "TRANSFER" and (not cleaned.get("from_wh") or not cleaned.get("to_wh")):
            raise forms.ValidationError("TRANSFER cần chọn cả 'From' và 'To'.")
        return cleaned


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["sku","name"]

# Query Panel
class SQLQueryForm(forms.Form):
    name = forms.CharField(max_length=128, required=False)
    sql  = forms.CharField(widget=forms.Textarea(attrs={"rows":10, "spellcheck":"false"}))

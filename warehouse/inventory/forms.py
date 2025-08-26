from django import forms
from django.utils import timezone
from .models import Product, Warehouse

class GenerateForm(forms.Form):
    sku  = forms.CharField(max_length=64)
    name = forms.CharField(max_length=255)
    import_date = forms.DateField(
        input_formats=["%d/%m/%Y"],
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "dd/mm/yyyy", "id": "id_import_date"})
    )
    qty  = forms.IntegerField(min_value=1, max_value=5000, initial=10)


class ScanMoveForm(forms.Form):
    ACTIONS = (("IN","IN"),("OUT","OUT"),("TRANSFER","TRANSFER"))
    action = forms.ChoiceField(choices=ACTIONS)
    barcode = forms.CharField(
        max_length=128,
        # ✅ barcode giờ là số: 4(code4)+6(ddmmyy)+5(seq) => ví dụ 000126082500001
        widget=forms.TextInput(attrs={"placeholder":"VD: 000126082500001", "autofocus":"autofocus"})
    )
    from_wh = forms.ModelChoiceField(queryset=Warehouse.objects.all(), required=False)
    to_wh   = forms.ModelChoiceField(queryset=Warehouse.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

# --- Scan session forms (flow mới) ---
ACTION_TYPE_MAP = {
    "IN": [
        ("purchase", "Nhập mua"),
        ("return_in", "Khách trả"),
        ("adjust_in", "Điều chỉnh +"),
    ],
    "OUT": [
        ("sale", "Xuất bán"),
        ("return_supplier", "Trả NCC"),
        ("adjust_out", "Điều chỉnh -"),
    ],
}

class ScanStartForm(forms.Form):
    action = forms.ChoiceField(choices=[("IN","IN"),("OUT","OUT")])
    action_type = forms.ChoiceField(choices=())
    wh = forms.ModelChoiceField(queryset=Warehouse.objects.all(), label="Kho")
    tag = forms.IntegerField(min_value=1, label="Đợt")

    def __init__(self, *args, tag_max=1, **kwargs):
        super().__init__(*args, **kwargs)
        act = (self.data.get("action") or self.initial.get("action") or "IN").upper()
        self.fields["action_type"].choices = ACTION_TYPE_MAP.get(act, [])
        self.fields["wh"].queryset = Warehouse.objects.all()
        # gợi ý & ràng buộc max (server vẫn sẽ re-check)
        self.fields["tag"].initial = max(1, int(tag_max))
        self.fields["tag"].widget.attrs.update({"min": 1, "max": int(tag_max)})

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") == "IN" and not cleaned.get("wh"):
            raise forms.ValidationError("IN cần chọn 'To kho'.")
        return cleaned

class ScanCodeForm(forms.Form):
    barcode = forms.CharField(
        max_length=128,
        widget=forms.TextInput(attrs={"placeholder":"Quét barcode...", "autofocus":"autofocus"})
    )




class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["sku","name"]

# Query Panel
class SQLQueryForm(forms.Form):
    name = forms.CharField(max_length=128, required=False)
    sql  = forms.CharField(widget=forms.Textarea(attrs={"rows":10, "spellcheck":"false"}))

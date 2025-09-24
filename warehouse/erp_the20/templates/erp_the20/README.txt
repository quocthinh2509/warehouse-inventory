Paste toàn bộ file/folder vào: erp_the20/templates/erp_the20/

Tên template:
- base.html
- dashboard.html
- departments.html
- positions.html
- locations.html
- employees.html
- includes/navbar.html

Mapping URL Django (ví dụ):
path("ui/", TemplateView.as_view(template_name="erp_the20/dashboard.html"), name="erp_dashboard")
path("ui/departments/", TemplateView.as_view(template_name="erp_the20/departments.html"), name="erp_departments")
path("ui/positions/", TemplateView.as_view(template_name="erp_the20/positions.html"), name="erp_positions")
path("ui/locations/", TemplateView.as_view(template_name="erp_the20/locations.html"), name="erp_locations")
path("ui/employees/", TemplateView.as_view(template_name="erp_the20/employees.html"), name="erp_employees")

Đặt API_BASE trong base.html cho khớp: window.API_BASE = "/erp/api"
Các endpoint giả định:
GET/POST   /departments/           PUT/DELETE /departments/{id}/
GET/POST   /positions/             PUT/DELETE /positions/{id}/
GET/POST   /worksites/             PUT/DELETE /worksites/{id}/
GET/POST   /employees/             PUT/DELETE /employees/{id}/
GET        /dashboard/

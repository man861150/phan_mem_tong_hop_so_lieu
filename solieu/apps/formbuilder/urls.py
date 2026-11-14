from django.urls import path

from apps.formbuilder import views

app_name = "formbuilder"

urlpatterns = [
    path("bieu-mau/", views.template_list, name="list"),
    path("bieu-mau/tao-moi/", views.template_create, name="create"),
    path("bieu-mau/<int:pk>/thiet-ke/", views.template_design, name="design"),
    path("bieu-mau/<int:pk>/luu/", views.template_save, name="save_draft"),
    path("bieu-mau/<int:pk>/xem-truoc/", views.template_preview, name="preview"),
    path(
        "bieu-mau/<int:pk>/xem-truoc/kiem-tra/",
        views.template_preview_check,
        name="preview_check",
    ),
    path("bieu-mau/<int:pk>/xuat-ban/", views.template_publish, name="publish"),
    path("bieu-mau/<int:pk>/nhan-ban/", views.template_duplicate, name="duplicate"),
    path("bieu-mau/<int:pk>/luu-tru/", views.template_archive, name="archive"),
    path("bieu-mau/<int:pk>/khoi-phuc/", views.template_restore, name="restore"),
    path("bieu-mau/<int:pk>/phien-ban/", views.template_versions, name="versions"),
    path(
        "bieu-mau/<int:pk>/phien-ban/<int:version_id>/lam-nhap/",
        views.template_draft_from,
        name="draft_from_version",
    ),
    path("bieu-mau/<int:pk>/phan/", views.section_create, name="section_create"),
    path(
        "bieu-mau/phan/<int:section_id>/sua/",
        views.section_update,
        name="section_update",
    ),
    path(
        "bieu-mau/phan/<int:section_id>/xoa/",
        views.section_delete,
        name="section_delete",
    ),
    path(
        "bieu-mau/phan/<int:section_id>/nhan-ban/",
        views.section_duplicate,
        name="section_duplicate",
    ),
    path("bieu-mau/<int:pk>/truong/", views.field_create, name="field_create"),
    path(
        "bieu-mau/truong/<int:field_id>/thuoc-tinh/",
        views.field_inspector,
        name="field_inspector",
    ),
    path(
        "bieu-mau/truong/<int:field_id>/sua/",
        views.field_update,
        name="field_update",
    ),
    path(
        "bieu-mau/truong/<int:field_id>/xoa/",
        views.field_delete,
        name="field_delete",
    ),
    path("bieu-mau/<int:pk>/sap-xep/", views.template_reorder, name="reorder"),
    path(
        "bieu-mau/truong/<int:field_id>/lua-chon/",
        views.option_create,
        name="option_create",
    ),
    path(
        "bieu-mau/lua-chon/<int:option_id>/xoa/",
        views.option_delete,
        name="option_delete",
    ),
    path("bieu-mau/<int:pk>/dieu-kien/", views.rule_create, name="rule_create"),
    path(
        "bieu-mau/dieu-kien/<int:rule_id>/xoa/",
        views.rule_delete,
        name="rule_delete",
    ),
    path(
        "bieu-mau/tep/<int:attachment_id>/",
        views.attachment_download,
        name="attachment",
    ),
]

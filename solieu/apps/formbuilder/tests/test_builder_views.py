from apps.formbuilder.models import FieldType, FormField
from apps.formbuilder.tests.base import FormFixture


class BuilderTests(FormFixture):
    def test_create_opens_the_designer_with_a_default_section(self):
        client = self.login(self.head)
        response = client.post(
            "/bieu-mau/tao-moi/",
            {
                "name": "Lớp huấn luyện",
                "function_type": "hoat_dong",
                "target": f"loai:{self.loai.pk}",
                "description": "Mẫu thử",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/thiet-ke/", response.url)
        page = client.get(response.url)
        self.assertContains(page, "Thông tin chung")
        self.assertContains(page, "Tên hoạt động")

    def test_duplicate_scope_is_a_vietnamese_error(self):
        self.make_template()
        client = self.login(self.head)
        response = client.post(
            "/bieu-mau/tao-moi/",
            {
                "name": "Lần hai",
                "function_type": "hoat_dong",
                "target": f"loai:{self.loai.pk}",
            },
        )
        self.assertContains(response, "Đã có biểu mẫu đang hoạt động cho phạm vi này.")

    def test_add_edit_delete_and_reorder_fields(self):
        template = self.make_template()
        client = self.login(self.head)
        for field_type in FieldType.values:
            response = client.post(
                f"/bieu-mau/{template.pk}/truong/",
                {"field_type": field_type},
            )
            self.assertEqual(response.status_code, 200, field_type)
        custom = FormField.objects.filter(
            version=template.current_draft,
            source="custom",
        )
        self.assertEqual(custom.count(), len(FieldType.values))
        text = custom.get(field_type="text")
        updated = client.post(
            f"/bieu-mau/truong/{text.pk}/sua/",
            {
                "label": "Số lượng đại biểu",
                "col_span": "6",
                "section": text.section_id,
                "required": "on",
            },
        )
        self.assertEqual(updated.status_code, 200)
        text.refresh_from_db()
        self.assertEqual(text.label, "Số lượng đại biểu")
        self.assertEqual(text.col_span, 6)
        self.assertTrue(text.required)
        select = custom.get(field_type="select")
        client.post(
            f"/bieu-mau/truong/{select.pk}/lua-chon/",
            {"label": "Trực tiếp", "value": "truc_tiep"},
        )
        duplicate = client.post(
            f"/bieu-mau/truong/{select.pk}/lua-chon/",
            {"label": "Trùng", "value": "truc_tiep"},
        )
        self.assertEqual(select.options.count(), 1)
        self.assertEqual(duplicate.status_code, 200)
        client.post(
            f"/bieu-mau/{template.pk}/phan/",
            {"title": "Thông tin bổ sung"},
        )
        sections = list(template.current_draft.sections.order_by("order", "id"))
        self.assertEqual(len(sections), 2)
        moved = client.post(
            f"/bieu-mau/{template.pk}/sap-xep/",
            {"field_id": text.pk, "section_id": sections[1].pk},
        )
        self.assertEqual(moved.status_code, 200)
        text.refresh_from_db()
        self.assertEqual(text.section_id, sections[1].pk)
        client.post(
            f"/bieu-mau/{template.pk}/sap-xep/",
            {"field_id": text.pk, "direction": "up"},
        )
        rejected = client.post(
            f"/bieu-mau/{template.pk}/sap-xep/",
            {"payload": '{"sections": [1], "fields": []}'},
        )
        self.assertEqual(rejected.status_code, 400)
        client.post(f"/bieu-mau/truong/{text.pk}/xoa/")
        self.assertFalse(FormField.objects.filter(pk=text.pk).exists())

    def test_autosave_returns_the_saved_fragment(self):
        template = self.make_template()
        client = self.login(self.head)
        response = client.post(
            f"/bieu-mau/{template.pk}/luu/",
            {
                "name": "Tên đã lưu",
                "description": "Mô tả",
                "layout_notes": "Ghi nội bộ",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "Đã lưu lúc")
        template.refresh_from_db()
        self.assertEqual(template.name, "Tên đã lưu")

    def test_label_is_escaped(self):
        template = self.make_template()
        field = template.current_draft.fields.get(core_key="ten")
        field.label = "<script>alert(1)</script>"
        field.save()
        page = self.login(self.head).get(f"/bieu-mau/{template.pk}/thiet-ke/")
        self.assertNotContains(page, "<script>alert(1)</script>", html=False)
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_empty_list_state(self):
        page = self.login(self.head).get("/bieu-mau/")
        self.assertContains(page, "Biểu mẫu nhập liệu")
        self.assertContains(page, "Chưa có biểu mẫu")
        self.assertContains(page, "Tạo biểu mẫu")

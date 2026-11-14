from django.core.exceptions import ValidationError

from apps.formbuilder.models import (
    FormField,
    FormFieldOption,
    FormRule,
    FormSection,
    FormTemplate,
)
from apps.formbuilder.services import (
    add_field,
    add_option,
    publish_template,
)
from apps.formbuilder.tests.base import FormFixture
from apps.formbuilder.validators import has_cycle


class ScopeTests(FormFixture):
    def test_scope_key_for_each_function(self):
        activity = self.make_template()
        self.assertEqual(activity.scope_key, f"hoat_dong:loai:{self.loai.pk}")
        generic = self.make_template(name="Mọi hoạt động", activity_type=None)
        self.assertEqual(generic.scope_key, "hoat_dong:*")
        indicator = self.make_template(
            name="Chỉ tiêu",
            function_type="chi_tieu",
            activity_type=None,
            group=self.nhom,
        )
        self.assertEqual(indicator.scope_key, f"chi_tieu:nhom:{self.nhom.pk}")
        month = self.make_template(
            name="Tháng",
            function_type="thang",
            activity_type=None,
        )
        self.assertEqual(month.scope_key, "thang:*")
        project = self.make_template(
            name="Dự án",
            function_type="du_an",
            activity_type=None,
        )
        self.assertEqual(project.scope_key, "du_an:*")

    def test_active_scope_is_unique(self):
        self.make_template()
        with self.assertRaises(ValidationError):
            self.make_template(name="Trùng phạm vi")

    def test_target_must_belong_to_the_department(self):
        with self.assertRaises(ValidationError):
            self.make_template(activity_type=self.loai_other)
        with self.assertRaises(ValidationError):
            self.make_template(
                name="Nhóm phòng khác",
                function_type="chi_tieu",
                activity_type=None,
                group=self.nhom_other,
            )


class FieldRuleTests(FormFixture):
    def test_key_width_and_core_lock(self):
        template = self.make_template()
        draft = template.current_draft
        section = draft.sections.get()
        field = add_field(draft, "text", section, label="Ghi chú thêm")
        self.assertTrue(field.key.startswith("cf_"))
        field.col_span = 13
        with self.assertRaises(ValidationError):
            field.save()
        field.col_span = 6
        field.key = "1bad"
        with self.assertRaises(ValidationError):
            field.save()
        core = draft.fields.get(core_key="ten")
        with self.assertRaises(ValidationError):
            core.delete()
        core.is_hidden_by_default = True
        with self.assertRaises(ValidationError):
            core.save()

    def test_published_children_are_immutable_and_publish_clones_a_draft(self):
        template = self.make_template()
        published = publish_template(template, self.head)
        template.refresh_from_db()
        self.assertEqual(published.status, "published")
        self.assertEqual(template.current_published_id, published.pk)
        self.assertEqual(template.current_draft.version, 2)
        self.assertEqual(template.current_draft.status, "draft")
        section = published.sections.get()
        section.title = "Đổi"
        with self.assertRaises(ValidationError):
            section.save()
        field = published.fields.get(core_key="ten")
        field.label = "Đổi"
        with self.assertRaises(ValidationError):
            field.save()

    def test_choice_options_and_cycles(self):
        template = self.make_template()
        draft = template.current_draft
        section = draft.sections.get()
        select = add_field(draft, "select", section, label="Kênh")
        add_option(select, "Trực tiếp", "truc_tiep")
        with self.assertRaises(ValidationError):
            FormFieldOption.objects.create(
                field=select,
                label="Trùng",
                value="truc_tiep",
                order=2,
            )
        other = add_field(draft, "text", section, label="Ghi chú")
        with self.assertRaises(ValidationError):
            FormRule.objects.create(
                version=draft,
                source_field_key=select.key,
                operator="equals",
                compare_value="truc_tiep",
                action="require",
                target_field_key=select.key,
                order=1,
            )
        first = FormRule.objects.create(
            version=draft,
            source_field_key=select.key,
            operator="equals",
            compare_value="truc_tiep",
            action="require",
            target_field_key=other.key,
            order=1,
        )
        second = FormRule(
            version=draft,
            source_field_key=other.key,
            operator="is_not_empty",
            action="show",
            target_field_key=select.key,
            order=2,
        )
        second.save()
        self.assertTrue(has_cycle([first, second]))

    def test_indicator_custom_field_must_be_per_row(self):
        template = self.make_template(
            name="Dòng chỉ tiêu",
            function_type="chi_tieu",
            activity_type=None,
            group=self.nhom,
        )
        draft = template.current_draft
        field = add_field(draft, "integer", draft.sections.get(), label="Số thêm")
        self.assertTrue(field.is_per_row)
        field.is_per_row = False
        with self.assertRaises(ValidationError):
            field.save()

    def test_section_must_keep_a_title(self):
        template = self.make_template()
        section = template.current_draft.sections.get()
        section.title = "   "
        with self.assertRaises(ValidationError):
            section.save()
        self.assertEqual(FormSection.objects.filter(pk=section.pk).count(), 1)
        self.assertEqual(FormTemplate.objects.count(), 1)
        self.assertGreater(
            FormField.objects.filter(version=template.current_draft).count(), 0
        )

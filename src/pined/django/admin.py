from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django import forms


def hide_related_actions(
    field: forms.Field,
    *,
    can_view: bool = False,
    can_add: bool = False,
    can_change: bool = False,
    can_delete: bool = False,
) -> None:
    """
    Hide the related-model actions on a related field's widget.

    The icons beside a `ForeignKey` or a `ManyToManyField` — add, change,
    delete, view — are all on by default, and each keyword left `False`
    takes one away. Belongs in `get_form` on a `ModelAdmin`, or in
    `get_formset` on an `InlineModelAdmin`.

    Args:
        field: A related model's form field, out of `form.base_fields`.
        can_view: Leave the "view" icon.
        can_add: Leave the "add" icon.
        can_change: Leave the "change" icon.
        can_delete: Leave the "delete" icon.

    Example:
        Every icon gone from "author" and "publisher"; "change" and
        "delete" gone from "genre":

        ```
        @admin.register(Book)
        class BookAdmin(admin.ModelAdmin):
            def get_form(self, request, *args, **kwargs):
                form = super().get_form(request, *args, **kwargs)
                genre = form.base_fields["genre"]

                for name in ("author", "publisher"):
                    hide_related_actions(form.base_fields[name])

                hide_related_actions(genre, can_add=True, can_view=True)
                return form
        ```
    """

    widget = field.widget
    widget.can_add_related = can_add
    widget.can_change_related = can_change
    widget.can_delete_related = can_delete
    widget.can_view_related = can_view

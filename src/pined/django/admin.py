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
    Hide available related-model-based actions from field's widget
    (ForeignKey, ManyToManyField).

    This method should be used in `get_form` or `get_formset` methods of
    ModelAdmin or InlineModelAdmin, respectively.

    Example:
        Hide every button for "author" and "publisher".
        Hide "delete" button for "genre".

        >>> @admin.register(Book)
        >>> class BookAdmin(admin.ModelAdmin):
        >>>     def get_form(self, request, *args, **kwargs):
        >>>         form = super().get_form(request, *args, **kwargs)
        >>>
        >>>         for name in ("author", "publisher"):
        >>>             hide_related_actions(form.base_fields[name])
        >>>
        >>>         hide_related_actions(form.base_fields["genre"], can_add=True, can_change=True, can_view=True)
        >>>         return form

    Args:
        field: form field of a related model, taken from `form.base_fields`
        can_view: leave "view" icon
        can_add: leave "add" icon
        can_change: leave "change" icon
        can_delete: leave "delete" icon
    """

    widget = field.widget
    widget.can_add_related = can_add
    widget.can_change_related = can_change
    widget.can_delete_related = can_delete
    widget.can_view_related = can_view

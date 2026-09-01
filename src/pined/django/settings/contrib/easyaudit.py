"""
django-easy-audit.

`easyaudit.settings` declares no defaults dict either; it reads each
setting with `getattr(settings, name, default)` at import. Nothing here
carries a value, for the same reason as django-axes.
"""

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from pined.django.settings.utils import UNSET, DropUnset, Unset


class EasyAuditSettings(DropUnset, BaseModel):
    """
    The `DJANGO_EASY_AUDIT_*` settings.

    The `_extra` pairs add to what the library already ignores, while the
    `_default` ones replace it wholesale.
    """

    django_easy_audit_watch_auth_events: Unset[bool] = UNSET
    django_easy_audit_watch_model_events: Unset[bool] = UNSET
    django_easy_audit_watch_request_events: Unset[bool] = UNSET

    django_easy_audit_registered_classes: Unset[list[str]] = UNSET
    django_easy_audit_unregistered_classes_default: Unset[list[str]] = UNSET
    django_easy_audit_unregistered_classes_extra: Unset[list[str]] = UNSET

    django_easy_audit_registered_urls: Unset[list[str]] = UNSET
    django_easy_audit_unregistered_urls_default: Unset[list[str]] = UNSET
    django_easy_audit_unregistered_urls_extra: Unset[list[str]] = UNSET

    django_easy_audit_logging_backend: Unset[str] = UNSET
    django_easy_audit_database_alias: Unset[str] = UNSET
    django_easy_audit_remote_addr_header: Unset[str] = UNSET
    django_easy_audit_readonly_events: Unset[bool] = UNSET
    django_easy_audit_user_db_constraint: Unset[bool] = UNSET

    django_easy_audit_crud_difference_callbacks: Unset[list[str]] = UNSET
    django_easy_audit_crud_event_no_changed_fields_skip: Unset[bool] = UNSET
    django_easy_audit_truncate_table_sql_statement: Unset[str] = UNSET

    django_easy_audit_admin_show_auth_events: Unset[bool] = UNSET
    django_easy_audit_admin_show_model_events: Unset[bool] = UNSET
    django_easy_audit_admin_show_request_events: Unset[bool] = UNSET

    django_easy_audit_crud_event_list_filter: Unset[list[str]] = UNSET
    django_easy_audit_crud_event_search_fields: Unset[list[str]] = UNSET
    django_easy_audit_login_event_list_filter: Unset[list[str]] = UNSET
    django_easy_audit_login_event_search_fields: Unset[list[str]] = UNSET
    django_easy_audit_request_event_list_filter: Unset[list[str]] = UNSET
    django_easy_audit_request_event_search_fields: Unset[list[str]] = UNSET

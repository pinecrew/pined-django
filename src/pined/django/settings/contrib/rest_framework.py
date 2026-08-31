"""
Django REST framework.

Field names follow `rest_framework.settings.DEFAULTS`.
"""

from typing import ClassVar

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from pined.django.settings.utils import DjangoModel, DropUnset


class RestFramework(DjangoModel):
    """
    The `REST_FRAMEWORK` dict.

    Every dotted path here is imported by `rest_framework` itself, so a
    project names its own classes rather than importing them.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset({"unauthenticated_user"})

    default_renderer_classes: list[str] | None = None
    default_parser_classes: list[str] | None = None
    default_authentication_classes: list[str] | None = None
    default_permission_classes: list[str] | None = None
    default_throttle_classes: list[str] | None = None
    default_throttle_rates: dict[str, str | None] | None = None
    default_content_negotiation_class: str | None = None
    default_metadata_class: str | None = None
    default_versioning_class: str | None = None
    default_pagination_class: str | None = None
    default_filter_backends: list[str] | None = None
    default_schema_class: str | None = None

    num_proxies: int | None = None
    page_size: int | None = None
    search_param: str | None = None
    ordering_param: str | None = None

    default_version: str | None = None
    allowed_versions: list[str] | None = None
    version_param: str | None = None

    unauthenticated_user: str | None = "django.contrib.auth.models.AnonymousUser"
    unauthenticated_token: str | None = None

    view_name_function: str | None = None
    view_description_function: str | None = None
    exception_handler: str | None = None
    non_field_errors_key: str | None = None

    test_request_renderer_classes: list[str] | None = None
    test_request_default_format: str | None = None

    url_format_override: str | None = None
    format_suffix_kwarg: str | None = None
    url_field_name: str | None = None

    date_format: str | None = None
    date_input_formats: list[str] | None = None
    datetime_format: str | None = None
    datetime_input_formats: list[str] | None = None
    time_format: str | None = None
    time_input_formats: list[str] | None = None
    duration_format: str | None = None

    unicode_json: bool | None = None
    compact_json: bool | None = None
    strict_json: bool | None = None
    coerce_decimal_to_string: bool | None = None
    coerce_bigint_to_string: bool | None = None
    uploaded_files_use_url: bool | None = None

    html_select_cutoff: int | None = None
    html_select_cutoff_text: str | None = None

    schema_coerce_path_pk: bool | None = None
    schema_coerce_method_names: dict[str, str] | None = None


class RestFrameworkSettings(DropUnset, BaseModel):
    """
    `REST_FRAMEWORK`.
    """

    rest_framework: RestFramework | None = None

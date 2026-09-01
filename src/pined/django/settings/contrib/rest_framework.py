"""
Django REST framework.

Field names follow `rest_framework.settings.DEFAULTS`.
"""

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from pined.django.settings.utils import UNSET, DjangoModel, DropUnset, Unset


class RestFramework(DjangoModel):
    """
    The `REST_FRAMEWORK` dict.

    Every dotted path here is imported by `rest_framework` itself, so a
    project names its own classes rather than importing them.
    """

    default_renderer_classes: Unset[list[str]] = UNSET
    default_parser_classes: Unset[list[str]] = UNSET
    default_authentication_classes: Unset[list[str]] = UNSET
    default_permission_classes: Unset[list[str]] = UNSET
    default_throttle_classes: Unset[list[str]] = UNSET
    default_throttle_rates: Unset[dict[str, str | None]] = UNSET
    default_content_negotiation_class: Unset[str] = UNSET
    default_metadata_class: Unset[str] = UNSET
    default_versioning_class: Unset[str] = UNSET
    default_pagination_class: Unset[str] = UNSET
    default_filter_backends: Unset[list[str]] = UNSET
    default_schema_class: Unset[str] = UNSET

    num_proxies: Unset[int] = UNSET
    page_size: Unset[int] = UNSET
    search_param: Unset[str] = UNSET
    ordering_param: Unset[str] = UNSET

    default_version: Unset[str] = UNSET
    allowed_versions: Unset[list[str]] = UNSET
    version_param: Unset[str] = UNSET

    unauthenticated_user: Unset[str | None] = UNSET
    unauthenticated_token: Unset[str] = UNSET

    view_name_function: Unset[str] = UNSET
    view_description_function: Unset[str] = UNSET
    exception_handler: Unset[str] = UNSET
    non_field_errors_key: Unset[str] = UNSET

    test_request_renderer_classes: Unset[list[str]] = UNSET
    test_request_default_format: Unset[str] = UNSET

    url_format_override: Unset[str] = UNSET
    format_suffix_kwarg: Unset[str] = UNSET
    url_field_name: Unset[str] = UNSET

    date_format: Unset[str] = UNSET
    date_input_formats: Unset[list[str]] = UNSET
    datetime_format: Unset[str] = UNSET
    datetime_input_formats: Unset[list[str]] = UNSET
    time_format: Unset[str] = UNSET
    time_input_formats: Unset[list[str]] = UNSET
    duration_format: Unset[str] = UNSET

    unicode_json: Unset[bool] = UNSET
    compact_json: Unset[bool] = UNSET
    strict_json: Unset[bool] = UNSET
    coerce_decimal_to_string: Unset[bool] = UNSET
    coerce_bigint_to_string: Unset[bool] = UNSET
    uploaded_files_use_url: Unset[bool] = UNSET

    html_select_cutoff: Unset[int] = UNSET
    html_select_cutoff_text: Unset[str] = UNSET

    schema_coerce_path_pk: Unset[bool] = UNSET
    schema_coerce_method_names: Unset[dict[str, str]] = UNSET


class RestFrameworkSettings(DropUnset, BaseModel):
    """
    `REST_FRAMEWORK`.
    """

    rest_framework: Unset[RestFramework] = UNSET

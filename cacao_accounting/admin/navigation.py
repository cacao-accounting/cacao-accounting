"""Registro central de la navegación de Configuración Global.

El registro mantiene la estructura funcional fuera del template y permite
reorganizar las rutas administrativas sin cambiar sus endpoints públicos.
"""

from __future__ import annotations

from dataclasses import dataclass

from cacao_accounting.i18n import _


@dataclass(frozen=True, slots=True)
class ConfigurationLink:
    """Enlace de una sección de configuración administrativa."""

    endpoint: str
    label: str
    module: str = "admin"
    required_permission: str = "configurar"
    cloud_only: bool = False


@dataclass(frozen=True, slots=True)
class ConfigurationSection:
    """Grupo funcional de enlaces de Configuración Global."""

    label: str
    icon: str
    links: tuple[ConfigurationLink, ...]


CONFIGURATION_SECTIONS: tuple[ConfigurationSection, ...] = (
    ConfigurationSection(
        label=_("Configuración General"),
        icon="bi bi-sliders",
        links=(
            ConfigurationLink("admin.lista_modulos", _("Módulos")),
            ConfigurationLink(
                "imports.index", _("Importaciones"), module="imports", required_permission="importar", cloud_only=True
            ),
            ConfigurationLink("admin.configuracion_idioma", _("Idioma del sistema")),
            ConfigurationLink("admin.external_document_validation_settings", _("Validación externa de documentos")),
            ConfigurationLink("admin.lista_grupos_terceros", _("Tipos de terceros")),
        ),
    ),
    ConfigurationSection(
        label=_("Correo Electrónico"),
        icon="bi bi-envelope",
        links=(
            ConfigurationLink("admin.email_settings", _("Correo electrónico"), cloud_only=True),
            ConfigurationLink("admin.email_log", _("Bitácora de correos"), cloud_only=True),
        ),
    ),
    ConfigurationSection(
        label=_("Precios"),
        icon="bi bi-tags",
        links=(
            ConfigurationLink("admin.lista_precios", _("Listas de precios")),
            ConfigurationLink("admin.precios_item", _("Precios por artículo")),
        ),
    ),
    ConfigurationSection(
        label=_("Compras"),
        icon="bi bi-cart-check",
        links=(
            ConfigurationLink("admin.config_conciliacion_compras", _("Conciliación y anticipos")),
            ConfigurationLink("admin.config_abastecimiento_compras", _("Comparativo de ofertas")),
        ),
    ),
    ConfigurationSection(
        label=_("Ventas"),
        icon="bi bi-receipt",
        links=(ConfigurationLink("admin.config_conciliacion_ventas", _("Conciliación de ventas")),),
    ),
    ConfigurationSection(
        label=_("Contabilidad"),
        icon="bi bi-journal-check",
        links=(
            ConfigurationLink("admin.cuentas_predeterminadas", _("Cuentas predeterminadas")),
            ConfigurationLink("admin.lista_reglas_mapeo_libros", _("Mapeo entre libros")),
            ConfigurationLink("admin.config_control_presupuestario", _("Control presupuestario")),
            ConfigurationLink("admin.config_approval_matrix", _("Matriz de aprobaciones")),
            ConfigurationLink("admin.lista_dimensiones", _("Dimensiones analíticas")),
        ),
    ),
    ConfigurationSection(
        label=_("Inventario"),
        icon="bi bi-box-seam",
        links=(ConfigurationLink("admin.configuracion_valuacion_inventario", _("Valuación de inventarios")),),
    ),
    ConfigurationSection(
        label=_("Bancos"),
        icon="bi bi-bank",
        links=(ConfigurationLink("bancos.bancos_reglas_matching", _("Reglas de matching bancario")),),
    ),
    ConfigurationSection(
        label=_("Series e Identificadores"),
        icon="bi bi-hash",
        links=(
            ConfigurationLink("contabilidad.naming_series_list", _("Series de numeración")),
            ConfigurationLink("contabilidad.external_counter_list", _("Contadores externos")),
        ),
    ),
    ConfigurationSection(
        label=_("Impuestos y Cargos"),
        icon="bi bi-percent",
        links=(
            ConfigurationLink("admin.lista_impuestos", _("Impuestos y cargos")),
            ConfigurationLink("admin.lista_plantillas_impuesto", _("Plantillas de impuestos")),
            ConfigurationLink("admin.lista_reglas_fiscales", _("Reglas fiscales")),
        ),
    ),
    ConfigurationSection(
        label=_("Seguridad de Sesión"),
        icon="bi bi-shield-lock",
        links=(
            ConfigurationLink(
                "admin.session_security_settings",
                _("Protección de orígenes"),
                cloud_only=True,
            ),
        ),
    ),
    ConfigurationSection(
        label=_("Usuarios y Permisos"),
        icon="bi bi-people",
        links=(
            ConfigurationLink("admin.lista_usuarios", _("Usuarios")),
            ConfigurationLink("admin.lista_roles", _("Roles y permisos")),
        ),
    ),
)

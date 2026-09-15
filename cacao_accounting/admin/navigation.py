"""Registro central de la navegación de Configuración Global.

El registro mantiene la estructura funcional fuera del template y permite
reorganizar las rutas administrativas sin cambiar sus endpoints públicos.
"""

from __future__ import annotations

from dataclasses import dataclass

from cacao_accounting.i18n import LazyText, _l


@dataclass(frozen=True, slots=True)
class ConfigurationLink:
    """Enlace de una sección de configuración administrativa."""

    endpoint: str
    label: LazyText
    module: str = "admin"
    required_permission: str = "configurar"
    cloud_only: bool = False


@dataclass(frozen=True, slots=True)
class ConfigurationSection:
    """Grupo funcional de enlaces de Configuración Global."""

    label: LazyText
    icon: str
    links: tuple[ConfigurationLink, ...]


CONFIGURATION_SECTIONS: tuple[ConfigurationSection, ...] = (
    ConfigurationSection(
        label=_l("Configuración General"),
        icon="bi bi-sliders",
        links=(
            ConfigurationLink("admin.lista_modulos", _l("Módulos")),
            ConfigurationLink(
                "imports.index", _l("Importaciones"), module="imports", required_permission="importar", cloud_only=True
            ),
            ConfigurationLink("admin.configuracion_idioma", _l("Idioma del sistema")),
            ConfigurationLink("admin.external_document_validation_settings", _l("Validación externa de documentos")),
            ConfigurationLink("admin.lista_grupos_terceros", _l("Tipos de terceros")),
        ),
    ),
    ConfigurationSection(
        label=_l("Correo Electrónico"),
        icon="bi bi-envelope",
        links=(
            ConfigurationLink("admin.email_settings", _l("Correo electrónico"), cloud_only=True),
            ConfigurationLink("admin.email_log", _l("Bitácora de correos"), cloud_only=True),
        ),
    ),
    ConfigurationSection(
        label=_l("Precios"),
        icon="bi bi-tags",
        links=(
            ConfigurationLink("admin.lista_precios", _l("Listas de precios")),
            ConfigurationLink("admin.precios_item", _l("Precios por artículo")),
        ),
    ),
    ConfigurationSection(
        label=_l("Compras"),
        icon="bi bi-cart-check",
        links=(
            ConfigurationLink("admin.config_conciliacion_compras", _l("Conciliación y anticipos")),
            ConfigurationLink("admin.config_abastecimiento_compras", _l("Comparativo de ofertas")),
        ),
    ),
    ConfigurationSection(
        label=_l("Ventas"),
        icon="bi bi-receipt",
        links=(ConfigurationLink("admin.config_conciliacion_ventas", _l("Conciliación de ventas")),),
    ),
    ConfigurationSection(
        label=_l("Contabilidad"),
        icon="bi bi-journal-check",
        links=(
            ConfigurationLink("admin.cuentas_predeterminadas", _l("Cuentas predeterminadas")),
            ConfigurationLink("admin.lista_reglas_mapeo_libros", _l("Mapeo entre libros")),
            ConfigurationLink("admin.config_control_presupuestario", _l("Control presupuestario")),
            ConfigurationLink("admin.config_approval_matrix", _l("Matriz de aprobaciones")),
            ConfigurationLink("admin.lista_dimensiones", _l("Dimensiones analíticas")),
        ),
    ),
    ConfigurationSection(
        label=_l("Inventario"),
        icon="bi bi-box-seam",
        links=(ConfigurationLink("admin.configuracion_valuacion_inventario", _l("Valuación de inventarios")),),
    ),
    ConfigurationSection(
        label=_l("Bancos"),
        icon="bi bi-bank",
        links=(ConfigurationLink("bancos.bancos_reglas_matching", _l("Reglas de matching bancario")),),
    ),
    ConfigurationSection(
        label=_l("Series e Identificadores"),
        icon="bi bi-hash",
        links=(
            ConfigurationLink("contabilidad.naming_series_list", _l("Series de numeración")),
            ConfigurationLink("contabilidad.external_counter_list", _l("Contadores externos")),
        ),
    ),
    ConfigurationSection(
        label=_l("Impuestos y Cargos"),
        icon="bi bi-percent",
        links=(
            ConfigurationLink("admin.lista_impuestos", _l("Impuestos y cargos")),
            ConfigurationLink("admin.lista_plantillas_impuesto", _l("Plantillas de impuestos")),
            ConfigurationLink("admin.lista_reglas_fiscales", _l("Reglas fiscales")),
        ),
    ),
    ConfigurationSection(
        label=_l("Seguridad de Sesión"),
        icon="bi bi-shield-lock",
        links=(
            ConfigurationLink(
                "admin.session_security_settings",
                _l("Protección de orígenes"),
                cloud_only=True,
            ),
        ),
    ),
    ConfigurationSection(
        label=_l("Usuarios y Permisos"),
        icon="bi bi-people",
        links=(
            ConfigurationLink("admin.lista_usuarios", _l("Usuarios")),
            ConfigurationLink("admin.lista_roles", _l("Roles y permisos")),
        ),
    ),
)

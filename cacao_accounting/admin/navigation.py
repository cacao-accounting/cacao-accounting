"""Registro central de la navegación de Configuración Global.

El registro mantiene la estructura funcional fuera del template y permite
reorganizar las rutas administrativas sin cambiar sus endpoints públicos.
"""

from __future__ import annotations

from dataclasses import dataclass


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
        label="Configuración General",
        icon="bi bi-sliders",
        links=(
            ConfigurationLink("admin.lista_modulos", "Módulos"),
            ConfigurationLink(
                "imports.index", "Importaciones", module="imports", required_permission="importar", cloud_only=True
            ),
            ConfigurationLink("admin.configuracion_idioma", "Idioma del sistema"),
            ConfigurationLink("admin.external_document_validation_settings", "Validación externa de documentos"),
            ConfigurationLink("admin.lista_grupos_terceros", "Tipos de terceros"),
        ),
    ),
    ConfigurationSection(
        label="Correo Electrónico",
        icon="bi bi-envelope",
        links=(
            ConfigurationLink("admin.email_settings", "Correo electrónico", cloud_only=True),
            ConfigurationLink("admin.email_log", "Bitácora de correos", cloud_only=True),
        ),
    ),
    ConfigurationSection(
        label="Precios",
        icon="bi bi-tags",
        links=(
            ConfigurationLink("admin.lista_precios", "Listas de precios"),
            ConfigurationLink("admin.precios_item", "Precios por artículo"),
        ),
    ),
    ConfigurationSection(
        label="Compras",
        icon="bi bi-cart-check",
        links=(
            ConfigurationLink("admin.config_conciliacion_compras", "Conciliación y anticipos"),
            ConfigurationLink("admin.config_abastecimiento_compras", "Comparativo de ofertas"),
        ),
    ),
    ConfigurationSection(
        label="Ventas",
        icon="bi bi-receipt",
        links=(ConfigurationLink("admin.config_conciliacion_ventas", "Conciliación de ventas"),),
    ),
    ConfigurationSection(
        label="Contabilidad",
        icon="bi bi-journal-check",
        links=(
            ConfigurationLink("admin.cuentas_predeterminadas", "Cuentas predeterminadas"),
            ConfigurationLink("admin.lista_reglas_mapeo_libros", "Mapeo entre libros"),
            ConfigurationLink("admin.config_control_presupuestario", "Control presupuestario"),
            ConfigurationLink("admin.config_approval_matrix", "Matriz de aprobaciones"),
        ),
    ),
    ConfigurationSection(
        label="Inventario",
        icon="bi bi-box-seam",
        links=(ConfigurationLink("admin.configuracion_valuacion_inventario", "Valuación de inventarios"),),
    ),
    ConfigurationSection(
        label="Bancos",
        icon="bi bi-bank",
        links=(ConfigurationLink("bancos.bancos_reglas_matching", "Reglas de matching bancario"),),
    ),
    ConfigurationSection(
        label="Series e Identificadores",
        icon="bi bi-hash",
        links=(
            ConfigurationLink("contabilidad.naming_series_list", "Series de numeración"),
            ConfigurationLink("contabilidad.external_counter_list", "Contadores externos"),
        ),
    ),
    ConfigurationSection(
        label="Impuestos y Cargos",
        icon="bi bi-percent",
        links=(
            ConfigurationLink("admin.lista_impuestos", "Impuestos y cargos"),
            ConfigurationLink("admin.lista_plantillas_impuesto", "Plantillas de impuestos"),
            ConfigurationLink("admin.lista_reglas_fiscales", "Reglas fiscales"),
        ),
    ),
    ConfigurationSection(
        label="Seguridad de Sesión",
        icon="bi bi-shield-lock",
        links=(
            ConfigurationLink(
                "admin.session_security_settings",
                "Protección de orígenes",
                cloud_only=True,
            ),
        ),
    ),
    ConfigurationSection(
        label="Usuarios y Permisos",
        icon="bi bi-people",
        links=(
            ConfigurationLink("admin.lista_usuarios", "Usuarios"),
            ConfigurationLink("admin.lista_roles", "Roles y permisos"),
        ),
    ),
)

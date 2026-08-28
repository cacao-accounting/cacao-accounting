from types import SimpleNamespace

from cacao_accounting.module_badges import module_badge


def test_module_badge_semantic_precedence():
    access = SimpleNamespace(access=True, consultar=True, autorizar=True)

    ok_badge = module_badge(access=access, required="access")
    assert ok_badge.status == "ok"
    assert ok_badge.css_class == "ca-status-ok"
    assert ok_badge.label == "Todo ok"

    pending_badge = module_badge(access=access, required="autorizar", pending_count=2)
    assert pending_badge.status == "pending_approval"
    assert pending_badge.css_class == "ca-status-pending-approval"
    assert pending_badge.title == "2 registro(s) pendiente(s) de aprobación"

    assert module_badge(access=access, required="access", requires_attention=True).status == "attention"


def test_module_badge_detects_no_access_and_view_only():
    no_access = SimpleNamespace(access=False, consultar=False, configurar=False)
    view_only = SimpleNamespace(access=True, consultar=True, configurar=False)

    assert module_badge(access=no_access, required="configurar").status == "no_access"
    assert module_badge(access=view_only, required="configurar", view_permission="consultar").status == "view_only"

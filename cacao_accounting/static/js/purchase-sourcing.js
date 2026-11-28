(() => {
  const form = document.querySelector('form[action*="/award"]');
  const reason = document.getElementById('authorization_reason');
  if (!form || !reason) return;

  // El servidor compara tarifas en moneda base; usar el mismo valor evita
  // exigir el motivo por precios nominales de monedas distintas.
  const comparableRateRaw = (input) => {
    if (input.dataset.baseRate !== undefined && input.dataset.baseRate !== "") return input.dataset.baseRate;
    return input.dataset.rate;
  };

  // Comparacion decimal exacta (Numeric(20,4)) sin Number para evitar perdida de precision.
  const normalizeRate = (raw) => {
    if (raw === undefined || raw === null) return null;
    const text = String(raw).trim();
    if (!/^[-+]?\d+(?:\.\d+)?$/.test(text)) return null;
    const sign = text.startsWith("-") ? "-" : "";
    const unsigned = text.replace(/^[-+]/, "");
    const [intPart, fracPart = ""] = unsigned.split(".");
    const frac = (fracPart + "0000").slice(0, 4);
    return sign + intPart.replace(/^0+(?=\d)/, "") + "." + frac;
  };

  const compareRates = (a, b) => {
    const na = normalizeRate(a);
    const nb = normalizeRate(b);
    if (na === null || nb === null) return null;
    if (na === nb) return 0;
    const pa = na.startsWith("-") ? -1 : 1;
    const pb = nb.startsWith("-") ? -1 : 1;
    if (pa !== pb) return pa < pb ? -1 : 1;
    const [ia, fa] = na.replace("-", "").split(".");
    const [ib, fb] = nb.replace("-", "").split(".");
    let cmp = 0;
    if (ia.length !== ib.length) cmp = ia.length < ib.length ? -1 : 1;
    else if (ia !== ib) cmp = ia < ib ? -1 : 1;
    else if (fa !== fb) cmp = fa < fb ? -1 : 1;
    return pa === -1 ? -cmp : cmp;
  };

  const updateReasonRequirement = () => {
    let override = false;
    const groups = [
      ...new Set(
        [...form.querySelectorAll('input[type="radio"][name^="award_item_"]')].map((input) => input.name),
      ),
    ];
    groups.forEach((name) => {
      const inputs = [...form.querySelectorAll(`input[name="${name}"]`)];
      const selected = inputs.find((input) => input.checked);
      if (!selected) return;
      const selectedRate = comparableRateRaw(selected);
      const hasHigherThanMin = inputs.some((input) => {
        const cmp = compareRates(comparableRateRaw(input), selectedRate);
        return cmp !== null && cmp < 0;
      });
      // selected > min => alguna otra es menor que selected
      if (hasHigherThanMin) override = true;
    });
    const insufficient = form.dataset.offersInsufficient === "true";
    reason.required = insufficient || override;
  };

  form.addEventListener('change', updateReasonRequirement);
  updateReasonRequirement();
})();

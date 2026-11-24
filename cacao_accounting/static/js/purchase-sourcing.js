(() => {
  const form = document.querySelector('form[action*="/award"]');
  const reason = document.getElementById('authorization_reason');
  if (!form || !reason) return;

  // El servidor compara tarifas en moneda base; usar el mismo valor evita
  // exigir el motivo por precios nominales de monedas distintas.
  const comparableRate = (input) => {
    const baseRate = Number(input.dataset.baseRate);
    if (input.dataset.baseRate !== undefined && !Number.isNaN(baseRate)) return baseRate;
    return Number(input.dataset.rate);
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
      const rates = inputs.map(comparableRate).filter((rate) => !Number.isNaN(rate));
      const selected = inputs.find((input) => input.checked);
      if (selected && rates.length && comparableRate(selected) > Math.min(...rates)) override = true;
    });
    const insufficient = form.dataset.offersInsufficient === 'true';
    reason.required = insufficient || override;
  };

  form.addEventListener('change', updateReasonRequirement);
  updateReasonRequirement();
})();

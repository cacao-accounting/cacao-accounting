(() => {
  const form = document.querySelector('form[action*="/award"]');
  const reason = document.getElementById('authorization_reason');
  if (!form || !reason) return;

  const updateReasonRequirement = () => {
    let override = false;
    const groups = [
      ...new Set(
        [...form.querySelectorAll('input[type="radio"][name^="award_item_"]')].map((input) => input.name),
      ),
    ];
    groups.forEach((name) => {
      const inputs = [...form.querySelectorAll(`input[name="${name}"]`)];
      const rates = inputs.map((input) => Number(input.dataset.rate)).filter((rate) => !Number.isNaN(rate));
      const selected = inputs.find((input) => input.checked);
      if (selected && rates.length && Number(selected.dataset.rate) > Math.min(...rates)) override = true;
    });
    const insufficient = form.dataset.offersInsufficient === 'true';
    reason.required = insufficient || override;
  };

  form.addEventListener('change', updateReasonRequirement);
  updateReasonRequirement();
})();

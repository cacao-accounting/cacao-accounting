(function initDashboardModule() {
  function buildFallbackConfig() {
    return {
      initialCompany: "",
      periods: [],
      companies: [],
      messages: {
        dashboardLoadError: "No se pudo cargar el dashboard.",
      },
      titles: {
        accounting: "Resumen financiero",
        banks: "Saldos bancarios",
        purchases: "Facturas por pagar",
        inventory: "Menor existencia",
        sales: "Mejores clientes",
      },
      headings: {
        accounting: ["Concepto", "Valor"],
        banks: ["Cuenta", "Saldo"],
        purchases: ["Factura", "Proveedor", "Pendiente"],
        inventory: ["Item", "Bodega", "Existencia"],
        sales: ["Cliente", "Total"],
      },
      chartLabels: {
        income: "Ingresos",
        expense: "Gastos",
        sales: "Ventas",
      },
      monthNames: ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
    };
  }

  function dashboardConfig() {
    const config = globalThis.dashboardConfig || {};
    return {
      ...buildFallbackConfig(),
      ...config,
      messages: { ...buildFallbackConfig().messages, ...config.messages },
      titles: { ...buildFallbackConfig().titles, ...config.titles },
      headings: { ...buildFallbackConfig().headings, ...config.headings },
      chartLabels: { ...buildFallbackConfig().chartLabels, ...config.chartLabels },
      monthNames: config.monthNames || buildFallbackConfig().monthNames,
      periods: config.periods || [],
      companies: config.companies || [],
    };
  }

  globalThis.dashboard = function dashboard() {
    const config = dashboardConfig();

    return {
      filters: {
        company: config.initialCompany,
        period: "",
      },
      periods: config.periods,
      sectionOrder: ["accounting", "banks", "purchases", "inventory", "sales"],
      loading: false,
      error: "",
      payload: { sections: {} },
      charts: {},
      init() {
        if (this.filters.company) {
          this.fetchData();
        }
      },
      onCompanyChange() {
        this.filters.period = "";
        this.fetchData();
      },
      availablePeriods() {
        const company = this.selectedCompany();
        if (!company) {
          return [];
        }
        return this.periods.filter((period) => period.entity === company.code);
      },
      selectedCompany() {
        return this.companies().find((company) => company.id === this.filters.company);
      },
      companies() {
        return config.companies;
      },
      fetchData() {
        if (!this.filters.company) {
          this.payload = { sections: {} };
          return;
        }

        this.loading = true;
        this.error = "";
        const params = new URLSearchParams({ company: this.filters.company });
        if (this.filters.period) {
          params.set("period", this.filters.period);
        }

        fetch(`/api/dashboard/data?${params.toString()}`)
          .then(async (response) => {
            const data = await response.json();
            return { ok: response.ok, data };
          })
          .then((result) => {
            if (!result.ok) {
              this.error = result.data.error || config.messages.dashboardLoadError;
              this.payload = { sections: {} };
              return;
            }
            this.payload = result.data;
            this.$nextTick(() => this.renderCharts());
          })
          .catch(() => {
            this.error = config.messages.dashboardLoadError;
          })
          .finally(() => {
            this.loading = false;
          });
      },
      section(key) {
        return this.payload.sections[key] || { visible: false, kpis: {}, tables: {}, charts: {}, actions: [] };
      },
      kpis(key) {
        return Object.values(this.section(key).kpis || {});
      },
      chartFor(key) {
        return key === "accounting" || key === "sales";
      },
      primaryTableTitle(key) {
        return config.titles[key] || "";
      },
      primaryRows(key) {
        const tables = this.section(key).tables || {};
        return {
          accounting: tables.summary || [],
          banks: tables.account_balances || [],
          purchases: tables.payables || tables.recent_invoices || [],
          inventory: tables.lowest_stock_items || [],
          sales: tables.top_customers || [],
        }[key] || [];
      },
      tableHeadings(key) {
        return config.headings[key] || [];
      },
      tableCells(key, row) {
        const money = (value) => this.formatCurrency(value, row.currency || this.companyCurrency());
        const cells = {
          accounting: [
            { key: "label", value: row.label },
            { key: "amount", value: row.currency ? money(row.amount) : this.formatNumber(row.amount), className: "text-end" },
          ],
          banks: [
            { key: "name", value: `${row.name || ""} ${row.account_no || ""}`.trim() },
            { key: "balance", value: money(row.balance), className: "text-end" },
          ],
          purchases: [
            { key: "document_no", value: row.document_no },
            { key: "party", value: row.party },
            { key: "outstanding", value: money(row.outstanding), className: "text-end" },
          ],
          inventory: [
            { key: "item_name", value: `${row.item_code} · ${row.item_name}` },
            { key: "warehouse", value: row.warehouse },
            { key: "current_qty", value: this.formatNumber(row.current_qty), className: "text-end" },
          ],
          sales: [
            { key: "name", value: row.name },
            { key: "total", value: money(row.total), className: "text-end" },
          ],
        };
        return cells[key] || [];
      },
      rowKey(row) {
        return row.document_no || row.item_code || row.name || row.label || JSON.stringify(row);
      },
      renderCharts() {
        this.renderAccountingChart();
        this.renderSalesChart();
      },
      renderAccountingChart() {
        const rows = this.section("accounting").charts?.monthly_result || [];
        this.renderLineChart(
          "accountingChart",
          rows.map((row) => this.monthName(row.month)),
          [
            { label: config.chartLabels.income, data: rows.map((row) => row.income), borderColor: "#2563eb" },
            { label: config.chartLabels.expense, data: rows.map((row) => row.expenses), borderColor: "#dc2626" },
          ]
        );
      },
      renderSalesChart() {
        const rows = this.section("sales").charts?.trend || [];
        this.renderLineChart(
          "salesChart",
          rows.map((row) => this.monthName(row.month)),
          [{ label: config.chartLabels.sales, data: rows.map((row) => row.total), borderColor: "#15803d" }]
        );
      },
      renderLineChart(canvasId, labels, datasets) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === "undefined") {
          return;
        }
        if (this.charts[canvasId]) {
          this.charts[canvasId].destroy();
        }
        this.charts[canvasId] = new Chart(canvas, {
          type: "line",
          data: {
            labels,
            datasets: datasets.map((dataset) => ({
              ...dataset,
              backgroundColor: "rgba(37, 99, 235, 0.08)",
              fill: false,
              tension: 0.35,
            })),
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: datasets.length > 1 } },
            scales: { y: { beginAtZero: true } },
          },
        });
      },
      formatKpi(kpi) {
        if (kpi.format === "money") {
          return this.formatCurrency(kpi.value, kpi.currency || this.companyCurrency());
        }
        return this.formatNumber(kpi.value);
      },
      formatCurrency(value, currency = "USD") {
        return new Intl.NumberFormat("es-NI", {
          style: "currency",
          currency,
          minimumFractionDigits: 2,
        }).format(Number(value || 0));
      },
      formatNumber(value) {
        return new Intl.NumberFormat("es-NI", { maximumFractionDigits: 2 }).format(Number(value || 0));
      },
      companyCurrency() {
        return this.payload.company?.currency || "USD";
      },
      monthName(month) {
        return config.monthNames[Number(month) - 1] || "";
      },
    };
  };
})();

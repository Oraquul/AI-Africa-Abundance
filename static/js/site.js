(function () {
  var form = document.querySelector("[data-oracle-filters]");
  if (form) {
    var rows = Array.prototype.slice.call(document.querySelectorAll("[data-oracle-row]"));
    var live = document.querySelector("[data-oracle-count]");
    var empty = document.querySelector("[data-oracle-empty]");

    function norm(value) {
      return (value || "").toLowerCase();
    }

    function apply() {
      var query = norm(form.querySelector("[name=q]").value);
      var domain = form.querySelector("[name=domain]").value;
      var status = form.querySelector("[name=status]").value;
      var layer = form.querySelector("[name=layer]").value;
      var shown = 0;
      rows.forEach(function (row) {
        var ok = true;
        if (domain && row.getAttribute("data-domain") !== domain) ok = false;
        if (status && row.getAttribute("data-status") !== status) ok = false;
        if (layer && row.getAttribute("data-layer") !== layer) ok = false;
        if (query && norm(row.getAttribute("data-search")).indexOf(query) === -1) ok = false;
        row.hidden = !ok;
        if (ok) shown += 1;
      });
      if (live) {
        live.textContent = "Showing " + shown + " of " + rows.length + " oracles.";
      }
      if (empty) empty.hidden = shown !== 0;
    }

    form.addEventListener("input", apply);
    form.addEventListener("change", apply);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      apply();
    });

    var params = new URLSearchParams(window.location.search);
    ["q", "domain", "status", "layer"].forEach(function (key) {
      var field = form.querySelector("[name=" + key + "]");
      if (field && params.has(key)) field.value = params.get(key);
    });
    apply();
  }

  var status = document.getElementById("copy-status");
  document.querySelectorAll("[data-copy-target]").forEach(function (button) {
    button.addEventListener("click", function () {
      var node = document.getElementById(button.getAttribute("data-copy-target"));
      if (!node) return;
      var text = node.textContent;
      var label = button.getAttribute("data-copy-label") || "Text";
      var previous = button.textContent;

      function done() {
        button.textContent = "Copied";
        if (status) status.textContent = label + " copied to the clipboard.";
        window.setTimeout(function () {
          button.textContent = previous;
        }, 2000);
      }

      function fallback() {
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("aria-hidden", "true");
        document.body.appendChild(area);
        area.select();
        var copied = false;
        try {
          copied = document.execCommand("copy");
        } catch (error) {
          copied = false;
        }
        document.body.removeChild(area);
        if (copied) {
          done();
        } else if (status) {
          status.textContent = "Automatic copy failed. Select the text and copy it manually.";
        }
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(fallback);
      } else {
        fallback();
      }
    });
  });
})();

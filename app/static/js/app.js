/* Contatos Fin - comportamento das telas (sem dependencias externas). */
(function () {
  "use strict";

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  function normalizar(texto) {
    return (texto || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  /* ---------------------------------------------------------------------
     Organizacao (campo "empresa"): busca enquanto digita; se nao existir, cadastra na hora.
     "ABEL" e "abel" sao a mesma empresa (o servidor confere de novo).
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-empresa]").forEach(function (caixa) {
    var campo = caixa.querySelector("input");
    var lista = caixa.querySelector(".sugestoes");
    var itens = [];
    var indice = -1;
    var temporizador = null;
    var ultimaBusca = "";

    function fechar() {
      lista.hidden = true;
      campo.setAttribute("aria-expanded", "false");
      indice = -1;
    }

    function marcar(i) {
      var opcoes = lista.querySelectorAll("li[data-acao]");
      opcoes.forEach(function (li, n) { li.setAttribute("aria-selected", n === i ? "true" : "false"); });
      indice = i;
    }

    function escolher(nome) {
      campo.value = nome;
      fechar();
    }

    function cadastrar(nome) {
      fetch(caixa.dataset.urlCriar || "/empresas/criar", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ nome: nome })
      })
        .then(function (r) { return r.json(); })
        .then(function (dados) {
          if (dados.erro) { alert(dados.erro); return; }
          escolher(dados.nome);
        })
        .catch(function () { alert("Não foi possível cadastrar a organização agora."); });
    }

    function desenhar(termo) {
      lista.innerHTML = "";
      var exata = itens.some(function (e) { return normalizar(e.nome) === normalizar(termo); });
      itens.forEach(function (e) {
        var li = document.createElement("li");
        li.setAttribute("role", "option");
        li.dataset.acao = "escolher";
        li.textContent = e.nome;
        li.addEventListener("mousedown", function (ev) { ev.preventDefault(); escolher(e.nome); });
        lista.appendChild(li);
      });
      if (!exata && termo.trim()) {
        var nova = document.createElement("li");
        nova.className = "sugestoes__nova";
        nova.setAttribute("role", "option");
        nova.dataset.acao = "cadastrar";
        nova.textContent = "+ Cadastrar “" + termo.trim() + "” como nova organização";
        nova.addEventListener("mousedown", function (ev) { ev.preventDefault(); cadastrar(termo.trim()); });
        lista.appendChild(nova);
      }
      if (!lista.children.length) { fechar(); return; }
      lista.hidden = false;
      campo.setAttribute("aria-expanded", "true");
      indice = -1;
    }

    function buscar() {
      var termo = campo.value;
      if (normalizar(termo).length < 2) { fechar(); return; }
      ultimaBusca = termo;
      fetch((caixa.dataset.urlBuscar || "/empresas/buscar") + "?q=" + encodeURIComponent(termo), { headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (dados) {
          if (termo !== ultimaBusca) return;
          itens = dados;
          desenhar(termo);
        })
        .catch(fechar);
    }

    campo.addEventListener("input", function () {
      clearTimeout(temporizador);
      temporizador = setTimeout(buscar, 180);
    });
    campo.addEventListener("keydown", function (ev) {
      var opcoes = lista.querySelectorAll("li[data-acao]");
      if (lista.hidden || !opcoes.length) return;
      if (ev.key === "ArrowDown") { ev.preventDefault(); marcar(Math.min(indice + 1, opcoes.length - 1)); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); marcar(Math.max(indice - 1, 0)); }
      else if (ev.key === "Enter" && indice >= 0) {
        ev.preventDefault();
        var li = opcoes[indice];
        if (li.dataset.acao === "cadastrar") cadastrar(campo.value.trim()); else escolher(li.textContent);
      } else if (ev.key === "Escape") { fechar(); }
    });
    campo.addEventListener("blur", function () { setTimeout(fechar, 120); });
  });

  /* ---------------------------------------------------------------------
     Foto: previa no retrato antes de salvar.
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-foto]").forEach(function (entrada) {
    entrada.addEventListener("change", function () {
      var arquivo = entrada.files && entrada.files[0];
      if (!arquivo) return;
      if (arquivo.size > 5 * 1024 * 1024) {
        alert("A foto passa de 5 MB. Escolha uma imagem menor.");
        entrada.value = "";
        return;
      }
      var retrato = entrada.closest(".seletor-foto").querySelector("[data-retrato]");
      var leitor = new FileReader();
      leitor.onload = function () {
        retrato.innerHTML = "";
        var img = document.createElement("img");
        img.src = leitor.result;
        img.alt = "Prévia da foto";
        retrato.appendChild(img);
      };
      leitor.readAsDataURL(arquivo);
      var remover = entrada.closest(".seletor-foto").querySelector('input[name="remover_foto"]');
      if (remover) remover.checked = false;
    });
  });

  /* ---------------------------------------------------------------------
     Mascaras leves (o servidor formata de novo ao salvar).
     --------------------------------------------------------------------- */
  var mascaras = {
    telefone: function (d) {
      d = d.slice(0, 11);
      if (d.length <= 2) return d.length ? "(" + d : "";
      if (d.length <= 6) return "(" + d.slice(0, 2) + ") " + d.slice(2);
      if (d.length <= 10) return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
      return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
    },
    cpf: function (d) {
      d = d.slice(0, 11);
      return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1-$2");
    },
    cnpj: function (d) {
      d = d.slice(0, 14);
      return d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
        .replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2");
    }
  };
  document.querySelectorAll("[data-mascara]").forEach(function (campo) {
    var tipo = campo.dataset.mascara;
    campo.addEventListener("input", function () {
      var valor = campo.value;
      // Telefone com texto (ramal, "+1 ...") fica livre.
      if (tipo === "telefone" && /[a-z+]/i.test(valor)) return;
      var digitos = valor.replace(/\D/g, "");
      campo.value = mascaras[tipo](digitos);
    });
  });

  /* ---------------------------------------------------------------------
     Confirmacao antes de acoes destrutivas e fechamento dos menus.
     --------------------------------------------------------------------- */
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (!window.confirm(form.dataset.confirmar)) ev.preventDefault();
    });
  });
  document.addEventListener("click", function (ev) {
    document.querySelectorAll("details.menu[open]").forEach(function (menu) {
      if (!menu.contains(ev.target)) menu.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") {
      document.querySelectorAll("details.menu[open]").forEach(function (m) { m.removeAttribute("open"); });
    }
  });

  /* Evita envio duplo do formulario da ficha. */
  document.querySelectorAll("[data-formulario-ficha]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var botao = form.querySelector('button[type="submit"]');
      if (botao) setTimeout(function () { botao.disabled = true; }, 0);
    });
  });
})();

/* Compartilhar no WhatsApp (teste): copiar texto e, onde o aparelho deixar,
   enviar o cartao .vcf pelo compartilhamento nativo. */
(function () {
  document.querySelectorAll("[data-compartilhar]").forEach(function (caixa) {
    var texto = caixa.querySelector("[data-whats-texto]").textContent;
    var copiar = caixa.querySelector("[data-whats-copiar]");
    var enviar = caixa.querySelector("[data-whats-enviar]");
    var vcf = caixa.querySelector("[data-whats-vcf]");

    copiar.addEventListener("click", function () {
      navigator.clipboard.writeText(texto).then(function () {
        copiar.textContent = "Copiado!";
        setTimeout(function () { copiar.textContent = "Copiar texto"; }, 1800);
      });
    });

    if (!navigator.canShare) return;
    var arquivo = null;
    fetch(vcf.href, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.blob() : null; })
      .then(function (blob) {
        if (!blob) return;
        var nome = (vcf.href.split("/").pop() || "contato.vcf");
        var candidato = new File([blob], nome, { type: "text/vcard" });
        if (navigator.canShare({ files: [candidato] })) {
          arquivo = candidato;
          enviar.hidden = false;
        }
      })
      .catch(function () {});

    enviar.addEventListener("click", function () {
      if (arquivo) navigator.share({ files: [arquivo] }).catch(function () {});
    });
  });
})();

/* Menu de tres barrinhas (celular): abre e fecha a lista vertical. */
(function () {
  var botao = document.querySelector("[data-menu-celular]");
  if (!botao) return;
  var topo = botao.closest(".topo");

  function alternar(abrir) {
    topo.classList.toggle("topo--aberto", abrir);
    botao.setAttribute("aria-expanded", abrir ? "true" : "false");
    botao.setAttribute("aria-label", abrir ? "Fechar menu" : "Abrir menu");
  }

  botao.addEventListener("click", function () {
    alternar(!topo.classList.contains("topo--aberto"));
  });
  document.addEventListener("click", function (e) {
    if (topo.classList.contains("topo--aberto") && !topo.contains(e.target)) alternar(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") alternar(false);
  });
})();

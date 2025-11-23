// static/js/notificacoes.js  (cole inteiro, sobrescrevendo o anterior)
(function () {
    function debugLog(...args) {
        if (window.location.hostname === "localhost" || window.location.hostname === "" || true) {
            console.log("[notificacoes.js]", ...args);
        }
    }

    // tenta inicializar, com retries caso o menu ainda não esteja no DOM
    function initNotificacoes() {
        const icone = document.getElementById("icone-notificacoes");
        const caixa = document.getElementById("caixa-notificacoes");
        const contador = document.getElementById("contador-notificacoes");
        const lista = document.getElementById("lista-notificacoes");

        if (!icone || !caixa || !contador || !lista) {
            debugLog("Elementos do menu NÃO encontrados ainda. Tentando novamente em 200ms.");
            return false;
        }

        debugLog("Elementos do menu encontrados. Inicializando.");

        // carregar notificações da API
        function carregarNotificacoes() {
            fetch("/api/notificacoes")
                .then(res => {
                    if (!res.ok) throw new Error("Resposta da API: " + res.status);
                    return res.json();
                })
                .then(data => {
                    debugLog("notificacoes recebidas:", data);
                    lista.innerHTML = "";

                    if (data.length === 0 || data.every(n => n.lida === 1)) {
                        contador.style.display = "none";
                    } else {
                        contador.textContent = data.filter(n => n.lida === 0).length;
                        contador.style.display = "inline-block";
                    }


                    // contador com limite visual (ex: 99+)
                    let total = data.length;
                    contador.textContent = total > 99 ? "99+" : String(total);
                    contador.style.display = "inline-block";

                    data.forEach(n => {
                        const div = document.createElement("div");
                        div.classList.add("notificacao-item");
                        const titulo = n.titulo || "";
                        const mensagem = n.mensagem || "";
                        const dataText = n.data || "";
                        div.innerHTML = `<strong>${titulo}</strong><br>${mensagem}<br><small>${dataText}</small>`;
                        // marcar not como lida ao clicar (opcional)
                        div.addEventListener("click", function () {
                            if (n.id) {
                                fetch("/notificacoes_ler/" + n.id, { method: "POST" })
                                    .then(() => {
                                        div.classList.add("lida");
                                        // atualizar contador: recarregar
                                        carregarNotificacoes();
                                    })
                                    .catch(err => debugLog("Erro marcando lida:", err));
                            }
                        });
                        lista.appendChild(div);
                    });
                })
                .catch(err => {
                    debugLog("Erro ao buscar notificações:", err);
                    lista.innerHTML = "<p>Erro ao carregar notificações.</p>";
                    contador.style.display = "none";
                });
        }

       icone.addEventListener("click", function () {
    // abre ou fecha a caixa
       caixa.style.display = caixa.style.display === "block" ? "none" : "block";

    // se abriu, marca todas como lidas
       if (caixa.style.display === "block") {
        fetch("/api/notificacoes")
            .then(res => res.json())
            .then(data => {
                marcarComoLidas(data);

                    // some o contador imediatamente
                    contador.style.display = "none";
                });
    }
});


        // fechar ao clicar fora
        document.addEventListener("click", function (e) {
            if (!icone.contains(e.target) && !caixa.contains(e.target)) {
                caixa.style.display = "none";
            }
        });

        // carregar inicialmente (mas não precisa recarregar a cada segundo)
        carregarNotificacoes();

        return true;
    }

    // tentativas curtas para cases onde o DOM é alterado dinamicamente
    let attempts = 0;
    const maxAttempts = 20;
    function tryInit() {
        attempts++;
        const ok = initNotificacoes();
        if (!ok && attempts < maxAttempts) {
            setTimeout(tryInit, 200);
        } else if (!ok) {
            console.warn("[notificacoes.js] Não conseguiu inicializar o sino após várias tentativas.");
        }
    }

    // start depois do DOMContentLoaded para segurança
    if (document.readyState === "complete" || document.readyState === "interactive") {
        tryInit();
    } else {
        document.addEventListener("DOMContentLoaded", tryInit);
    }
})();

function marcarComoLidas(notificacoes) {
    notificacoes.forEach(n => {
        if (n.lida === 0) { 
            fetch(`/notificacoes_ler/${n.id}`, { method: "POST" });
        }
    });
}

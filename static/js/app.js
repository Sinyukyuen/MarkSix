const form = document.getElementById("generate-form");
const drawsInput = document.getElementById("draws");
const ticketsInput = document.getElementById("tickets");
const drawsValue = document.getElementById("draws-value");
const ticketsValue = document.getElementById("tickets-value");
const submitBtn = document.getElementById("submit-btn");
const spinner = submitBtn.querySelector(".spinner");
const btnLabel = submitBtn.querySelector(".btn-label");
const errorBanner = document.getElementById("error");
const resultsSection = document.getElementById("results");
const disclaimer = document.getElementById("disclaimer");

function ballElement(number, color, { small = false, special = false } = {}) {
  const el = document.createElement("span");
  el.className = `ball ${color}${small ? " small" : ""}${special ? " special" : ""}`;
  el.textContent = String(number).padStart(2, "0");
  el.title = `Ball ${number}`;
  return el;
}

function renderBalls(container, numbers, special = null) {
  container.replaceChildren();
  numbers.forEach((num) => {
    container.appendChild(ballElement(num, ballColorFromNumber(num)));
  });
  if (special !== null) {
    container.appendChild(
      ballElement(special, ballColorFromNumber(special), { special: true })
    );
  }
}

function setLoading(loading) {
  submitBtn.disabled = loading;
  spinner.hidden = !loading;
  btnLabel.textContent = loading ? "Generating..." : "Generate Numbers";
}

drawsInput.addEventListener("input", () => {
  drawsValue.textContent = drawsInput.value;
});

ticketsInput.addEventListener("input", () => {
  ticketsValue.textContent = ticketsInput.value;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBanner.hidden = true;
  setLoading(true);

  const payload = {
    strategy: document.getElementById("strategy").value,
    draws: Number(drawsInput.value),
    tickets: Number(ticketsInput.value),
    refresh: document.getElementById("refresh").checked,
  };

  const seedRaw = document.getElementById("seed").value.trim();
  if (seedRaw !== "") {
    payload.seed = Number(seedRaw);
  }

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed");
    }
    renderResults(data);
  } catch (error) {
    errorBanner.textContent = error.message;
    errorBanner.hidden = false;
  } finally {
    setLoading(false);
  }
});

function renderResults(data) {
  disclaimer.textContent = data.disclaimer;
  resultsSection.hidden = false;

  document.getElementById("latest-id").textContent = data.latest_draw.draw_id;
  document.getElementById("latest-date").textContent = data.latest_draw.draw_date;
  document.getElementById("draw-count").textContent = `${data.draw_count} draws analyzed`;

  const latestBalls = document.getElementById("latest-balls");
  renderBalls(latestBalls, data.latest_draw.numbers, data.latest_draw.special);

  const topBody = document.getElementById("top-numbers");
  topBody.replaceChildren();
  data.top_numbers.forEach((item) => {
    const row = document.createElement("tr");
    const ballCell = document.createElement("td");
    ballCell.appendChild(ballElement(item.number, item.color, { small: true }));
    row.appendChild(ballCell);
    ["frequency", "gap", "pair_strength", "composite_score"].forEach((key) => {
      const cell = document.createElement("td");
      cell.textContent = item[key];
      row.appendChild(cell);
    });
    topBody.appendChild(row);
  });

  const ticketGrid = document.getElementById("ticket-grid");
  ticketGrid.replaceChildren();
  data.tickets.forEach((ticket, index) => {
    const card = document.createElement("article");
    card.className = "ticket-card";

    const header = document.createElement("div");
    header.className = "ticket-header";
    header.innerHTML = `<strong>Ticket ${index + 1}</strong><span class="ticket-metrics">score ${ticket.ticket_score} &middot; balance ${ticket.balance}</span>`;
    card.appendChild(header);

    const balls = document.createElement("div");
    balls.className = "ball-row";
    ticket.numbers.forEach((num) => {
      balls.appendChild(ballElement(num, ballColorFromNumber(num), { small: true }));
    });
    balls.appendChild(
      ballElement(ticket.special, ballColorFromNumber(ticket.special), { small: true, special: true })
    );
    card.appendChild(balls);
    ticketGrid.appendChild(card);
  });

  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function ballColorFromNumber(number) {
  const colorIndex = Math.floor((((number - 1) + Math.floor((number - 1) / 10)) % 6) / 2);
  return ["red", "blue", "green"][colorIndex];
}

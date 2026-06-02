const formatCurrency = (value) =>
  new Intl.NumberFormat("en-MY", {
    style: "currency",
    currency: "MYR",
    maximumFractionDigits: 0,
  }).format(value);

const sliders = {
  flight: document.querySelector('[data-key="flight"]'),
  hotel: document.querySelector('[data-key="hotel"]'),
  activities: document.querySelector('[data-key="activities"]'),
  food: document.querySelector('[data-key="food"]'),
};

const labels = {
  flight: document.querySelector("#flightValue"),
  hotel: document.querySelector("#hotelValue"),
  activities: document.querySelector("#activitiesValue"),
  food: document.querySelector("#foodValue"),
};

const bars = {
  flight: document.querySelector("#flightBar"),
  hotel: document.querySelector("#hotelBar"),
  activities: document.querySelector("#activitiesBar"),
  food: document.querySelector("#foodBar"),
};

const totalBudgetLabel = document.querySelector("#totalBudgetLabel");
const checkoutTotal = document.querySelector("#checkoutTotal");
const savingAmount = document.querySelector("#savingAmount");
const refreshTitle = document.querySelector("#refreshTitle");
const refreshCopy = document.querySelector("#refreshCopy");
const budgetInput = document.querySelector("#budgetInput");
const destinationInput = document.querySelector("#destinationInput");
const travellerInput = document.querySelector("#travellerInput");
const apiStatus = document.querySelector("#apiStatus");
const authModal = document.querySelector("#authModal");
const openLoginButton = document.querySelector("#openLoginButton");
const accountChip = document.querySelector("#accountChip");
const accountInitial = document.querySelector("#accountInitial");
const accountName = document.querySelector("#accountName");
const accountActionButton = document.querySelector("#accountActionButton");
const accountStatusCard = document.querySelector("#accountStatusCard");
const accountStatusTitle = document.querySelector("#accountStatusTitle");
const accountStatusCopy = document.querySelector("#accountStatusCopy");
const authForm = document.querySelector("#authForm");
const authSubmitButton = document.querySelector("#authSubmitButton");
const authMessage = document.querySelector("#authMessage");
const authName = document.querySelector("#authName");
const authEmail = document.querySelector("#authEmail");
const checkoutButton = document.querySelector("#checkoutButton");
const monthlyChart = document.querySelector("#monthlyChart");
const peakMonthLabel = document.querySelector("#peakMonthLabel");
const peakMonthValue = document.querySelector("#peakMonthValue");
const peakMonthCopy = document.querySelector("#peakMonthCopy");
const totalUsersLabel = document.querySelector("#totalUsersLabel");
const averageUsersLabel = document.querySelector("#averageUsersLabel");
const peakUpliftLabel = document.querySelector("#peakUpliftLabel");
const chartTitle = document.querySelector("#chartTitle");
const chartSubtitle = document.querySelector("#chartSubtitle");
const chartBadge = document.querySelector("#chartBadge");
const analysisList = document.querySelector("#analysisList");
const topMonthsList = document.querySelector("#topMonthsList");

let totalBudget = Number(budgetInput.value);
let activePersona = "solo";
let authMode = "login";
let currentUser = null;
let activeInsightMetric = "activeUsers";

const personaDefaults = {
  solo: {
    destination: "Bali",
    travellers: 1,
    budget: 2500,
    split: { flight: 900, hotel: 800, activities: 500, food: 300 },
    status: "Fallback-ready API response schema",
  },
  family: {
    destination: "Langkawi",
    travellers: 4,
    budget: 7800,
    split: { flight: 2600, hotel: 2900, activities: 1500, food: 800 },
    status: "Family workspace package loaded",
  },
  team: {
    destination: "Da Nang",
    travellers: 8,
    budget: 12400,
    split: { flight: 4300, hotel: 3600, activities: 2800, food: 1700 },
    status: "Organization bundle package loaded",
  },
};

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const insightData = {
  activeUsers: {
    title: "Active users by month",
    unit: "users",
    totalLabel: "Total active users",
    averageLabel: "Average per month",
    values: [4120, 4680, 5220, 6100, 7420, 9880, 12480, 11640, 8340, 6810, 5480, 6560],
    reason: "School holidays and summer travel demand create the strongest user activity period.",
    summary: [
      "July has the highest active users.",
      "Travel demand rises from May to August.",
      "Campaigns should start before the peak month.",
    ],
  },
  tripSearches: {
    title: "Trip searches by month",
    unit: "searches",
    totalLabel: "Total trip searches",
    averageLabel: "Average per month",
    values: [15800, 17600, 19200, 22400, 29800, 38400, 46200, 42100, 31600, 26300, 21400, 28700],
    reason: "Users research more heavily in July before confirming flight, hotel, and activity bundles.",
    summary: [
      "July has the highest trip search activity.",
      "Search demand starts climbing from May.",
      "AI package suggestions should be tuned before peak search season.",
    ],
  },
  bookings: {
    title: "Bookings by month",
    unit: "bookings",
    totalLabel: "Total bookings",
    averageLabel: "Average per month",
    values: [980, 1120, 1240, 1380, 1840, 2380, 2960, 2740, 2050, 1660, 1420, 1920],
    reason: "Bookings peak in July, matching the strongest active user and search period.",
    summary: [
      "July has the highest booking conversion volume.",
      "June and August remain strong supporting months.",
      "Bundle discounts can be scheduled around the July peak.",
    ],
  },
};

function setSliderRange(key, value, budget) {
  const slider = sliders[key];
  const lowRatio = key === "flight" ? 0.18 : 0.08;
  const highRatio = key === "flight" ? 0.54 : 0.48;
  slider.min = Math.round((budget * lowRatio) / 50) * 50;
  slider.max = Math.round((budget * highRatio) / 50) * 50;
  slider.value = value;
}

function values() {
  return Object.fromEntries(Object.entries(sliders).map(([key, slider]) => [key, Number(slider.value)]));
}

function balanceBudget(changedKey) {
  let current = values();
  let diff = totalBudget - Object.values(current).reduce((total, value) => total + value, 0);
  const order = ["hotel", "activities", "food", "flight"].filter((key) => key !== changedKey);

  for (const key of order) {
    if (diff === 0) break;
    const slider = sliders[key];
    const min = Number(slider.min);
    const max = Number(slider.max);
    const next = Math.max(min, Math.min(max, Number(slider.value) + diff));
    slider.value = Math.round(next / 50) * 50;
    current = values();
    diff = totalBudget - Object.values(current).reduce((total, value) => total + value, 0);
  }

  const balancedSum = Object.values(values()).reduce((total, value) => total + value, 0);
  if (balancedSum !== totalBudget) {
    sliders.food.value = Number(sliders.food.value) + (totalBudget - balancedSum);
  }
}

function updateBudgetUI(changedKey = "flight") {
  const current = values();

  Object.entries(current).forEach(([key, value]) => {
    labels[key].textContent = formatCurrency(value);
    const percent = Math.max(14, Math.round((value / totalBudget) * 100));
    bars[key].style.setProperty("--bar", `${percent}%`);
  });

  totalBudgetLabel.textContent = formatCurrency(totalBudget);
  checkoutTotal.textContent = formatCurrency(totalBudget);
  const separateTotal = activePersona === "solo" ? 2920 : activePersona === "family" ? 8920 : 14250;
  savingAmount.textContent = formatCurrency(Math.max(0, separateTotal - totalBudget));

  const flightLean = current.flight < totalBudget * 0.34;
  const hotelLean = current.hotel > totalBudget * 0.34;
  const activityLean = current.activities > totalBudget * 0.24;

  if (flightLean && hotelLean) {
    refreshTitle.textContent = "Hotel upgrade unlocked";
    refreshCopy.textContent = "Flight savings are reallocated into a stronger stay while the total budget stays fixed.";
  } else if (activityLean) {
    refreshTitle.textContent = "Activity bundle expanded";
    refreshCopy.textContent = "Extra activity budget adds a guided local experience and preserves the package total.";
  } else {
    refreshTitle.textContent = "Balanced value route selected";
    refreshCopy.textContent = "Trekku keeps the flight, stay, activities, and food plan aligned to the locked budget.";
  }

  apiStatus.textContent = changedKey === "form" ? "Bundle search response refreshed" : personaDefaults[activePersona].status;
}

function formatCompact(value) {
  return new Intl.NumberFormat("en-MY", {
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);
}

function renderInsightDashboard(metricKey = activeInsightMetric) {
  activeInsightMetric = metricKey;
  const metric = insightData[metricKey];
  const max = Math.max(...metric.values);
  const total = metric.values.reduce((sum, value) => sum + value, 0);
  const average = Math.round(total / metric.values.length);
  const peakIndex = metric.values.indexOf(max);
  const peakMonth = monthNames[peakIndex];
  const peakUplift = Math.round(((max - average) / average) * 100);

  document.querySelectorAll("[data-insight-metric]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.insightMetric === metricKey);
  });

  peakMonthLabel.textContent = peakMonth;
  peakMonthValue.textContent = `${formatCompact(max)} ${metric.unit}`;
  peakMonthCopy.textContent = metric.reason;
  totalUsersLabel.textContent = formatCompact(total);
  averageUsersLabel.textContent = formatCompact(average);
  peakUpliftLabel.textContent = `${peakUplift}%`;
  chartTitle.textContent = metric.title;
  chartSubtitle.textContent = `${peakMonth} is currently the strongest month for ${metric.unit}.`;
  chartBadge.textContent = `Peak: ${peakMonth}`;

  monthlyChart.innerHTML = metric.values
    .map((value, index) => {
      const height = Math.max(12, Math.round((value / max) * 230));
      const isPeak = index === peakIndex ? " is-peak is-selected" : "";
      return `
        <div class="month-bar${isPeak}">
          <button type="button" style="--height: ${height}px" data-month="${monthNames[index]}" data-value="${formatCompact(value)}"></button>
          <span>${monthNames[index]}</span>
          <small>${formatCompact(value)}</small>
        </div>
      `;
    })
    .join("");

  analysisList.innerHTML = metric.summary
    .map((item) => `<li><svg><use href="#icon-check"></use></svg> ${item}</li>`)
    .join("");

  const topMonths = metric.values
    .map((value, index) => ({ month: monthNames[index], value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 3);

  topMonthsList.innerHTML = topMonths.map((item) => `<li>${item.month} - ${formatCompact(item.value)} ${metric.unit}</li>`).join("");

  monthlyChart.querySelectorAll(".month-bar button").forEach((button) => {
    button.addEventListener("click", () => {
      monthlyChart.querySelectorAll(".month-bar").forEach((bar) => bar.classList.remove("is-selected"));
      button.closest(".month-bar").classList.add("is-selected");
      chartSubtitle.textContent = `${button.dataset.month} recorded ${button.dataset.value} ${metric.unit}.`;
    });
  });
}

function openAuthModal(mode = "login") {
  setAuthMode(mode);
  authModal.hidden = false;
  document.body.style.overflow = "hidden";
  setTimeout(() => authEmail.focus(), 0);
}

function closeAuthModal() {
  authModal.hidden = true;
  document.body.style.overflow = "";
}

function setAuthMode(mode) {
  authMode = mode;
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.authMode === mode);
  });
  document.querySelectorAll(".signup-only").forEach((field) => {
    field.hidden = mode !== "signup";
  });
  authSubmitButton.textContent = mode === "signup" ? "Create account" : "Login to account";
  authMessage.textContent =
    mode === "signup"
      ? "Demo creates a local session. Backend handoff: Firebase createUserWithEmailAndPassword."
      : "Demo mode uses local UI state. Backend handoff: Firebase signInWithEmailAndPassword.";
}

function setAuthenticatedUser(user) {
  currentUser = user;
  localStorage.setItem("trekkuUser", JSON.stringify(user));

  openLoginButton.hidden = true;
  accountChip.hidden = false;
  accountInitial.textContent = user.name.slice(0, 1).toUpperCase();
  accountName.textContent = user.name.split(" ")[0];

  accountStatusCard.classList.add("is-authenticated");
  accountStatusTitle.textContent = `Signed in as ${user.name}`;
  accountStatusCopy.textContent =
    "My Trips, saved itineraries, member invitations, and checkout are unlocked for this account.";
  accountActionButton.textContent = "View saved trips";
  checkoutButton.textContent = "Proceed to checkout";
  authMessage.textContent = "Login successful. Account session is active for the prototype.";
}

function restoreAuthenticatedUser() {
  const saved = localStorage.getItem("trekkuUser");
  if (!saved) return;

  try {
    setAuthenticatedUser(JSON.parse(saved));
  } catch {
    localStorage.removeItem("trekkuUser");
  }
}

Object.entries(sliders).forEach(([key, slider]) => {
  slider.addEventListener("input", () => {
    balanceBudget(key);
    updateBudgetUI(key);
  });
});

document.querySelectorAll(".persona-card").forEach((card) => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".persona-card").forEach((item) => item.classList.remove("is-active"));
    card.classList.add("is-active");
    activePersona = card.dataset.persona;

    const next = personaDefaults[activePersona];
    destinationInput.value = next.destination;
    travellerInput.value = next.travellers;
    budgetInput.value = next.budget;
    totalBudget = next.budget;

    Object.entries(next.split).forEach(([key, value]) => {
      setSliderRange(key, value, totalBudget);
    });

    updateBudgetUI("persona");
  });
});

openLoginButton.addEventListener("click", () => openAuthModal("login"));
accountActionButton.addEventListener("click", () => {
  if (currentUser) {
    document.querySelector("#itinerary").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  openAuthModal("login");
});

accountChip.addEventListener("click", () => {
  const shouldSignOut = confirm("Sign out from this Trekku prototype account?");
  if (!shouldSignOut) return;

  currentUser = null;
  localStorage.removeItem("trekkuUser");
  openLoginButton.hidden = false;
  accountChip.hidden = true;
  accountStatusCard.classList.remove("is-authenticated");
  accountStatusTitle.textContent = "Guest browsing mode";
  accountStatusCopy.textContent =
    "Users can explore packages first, then log in before saving itineraries, inviting members, or checking out.";
  accountActionButton.textContent = "Login to continue";
  checkoutButton.textContent = "Login to checkout";
});

document.querySelectorAll("[data-close-auth]").forEach((element) => {
  element.addEventListener("click", closeAuthModal);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !authModal.hidden) {
    closeAuthModal();
  }
});

document.querySelectorAll("[data-auth-mode]").forEach((button) => {
  button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
});

authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name =
    authMode === "signup"
      ? authName.value.trim() || "Trekku User"
      : authEmail.value.split("@")[0].replace(/[._-]/g, " ") || "Trekku User";
  const displayName = name
    .split(" ")
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");

  setAuthenticatedUser({
    name: displayName,
    email: authEmail.value,
    provider: authMode === "signup" ? "email_signup" : "email_login",
  });
  closeAuthModal();
  document.querySelector("#account").scrollIntoView({ behavior: "smooth", block: "start" });
});

document.querySelector("#demoGoogleButton").addEventListener("click", () => {
  setAuthenticatedUser({
    name: "Daniel Student",
    email: "daniel@trekku.demo",
    provider: "google_demo",
  });
  closeAuthModal();
  document.querySelector("#account").scrollIntoView({ behavior: "smooth", block: "start" });
});

checkoutButton.addEventListener("click", () => {
  if (!currentUser) {
    checkoutButton.textContent = "Login required";
    openAuthModal("login");
    return;
  }
  checkoutButton.textContent = "Checkout session ready";
});

document.querySelector("#tripForm").addEventListener("submit", (event) => {
  event.preventDefault();
  totalBudget = Number(budgetInput.value) || totalBudget;
  const current = values();
  const ratio = totalBudget / Object.values(current).reduce((total, value) => total + value, 0);

  Object.entries(sliders).forEach(([key, slider]) => {
    const nextValue = Math.round((Number(slider.value) * ratio) / 50) * 50;
    setSliderRange(key, nextValue, totalBudget);
  });

  balanceBudget("form");
  updateBudgetUI("form");
});

budgetInput.addEventListener("change", () => {
  totalBudget = Number(budgetInput.value) || totalBudget;
  document.querySelector("#tripForm").dispatchEvent(new Event("submit"));
});

document.querySelectorAll(".select-package").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".package-card").forEach((card) => card.classList.remove("is-selected"));
    button.closest(".package-card").classList.add("is-selected");
    document.querySelector("#budget").scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

document.querySelectorAll(".segmented button").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.insightMetric) return;
    document.querySelectorAll(".segmented button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
  });
});

document.querySelectorAll("[data-insight-metric]").forEach((button) => {
  button.addEventListener("click", () => renderInsightDashboard(button.dataset.insightMetric));
});

document.querySelectorAll(".day-tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".day-tabs button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
  });
});

document.querySelector("#weatherButton").addEventListener("click", () => {
  const timeline = document.querySelector("#timeline");
  timeline.children[2].querySelector("strong").textContent = "Indoor cafe and art market route";
  timeline.children[2].querySelector("span").textContent = "Rain-safe replacement, 12 min from hotel";
  timeline.children[2].querySelector("b").textContent = "RM 38";
  document.querySelector("#notificationCopy").textContent = "Indoor route accepted. Day 1 has been reshuffled around the weather alert.";
});

checkoutButton.textContent = "Login to checkout";
restoreAuthenticatedUser();
renderInsightDashboard();
updateBudgetUI();

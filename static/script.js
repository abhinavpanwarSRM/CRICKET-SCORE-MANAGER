function toggleWicketType() {
  const checkbox = document.getElementById("is_wicket");
  const div = document.getElementById("wicket_type_div");
  div.style.display = checkbox.checked ? "block" : "none";
  toggleRunOutBatsman();
}

function toggleRunOutBatsman() {
  const wicketType = document.getElementById("wicket_type");
  const runOutDiv = document.getElementById("run_out_batsman_div");
  runOutDiv.style.display = wicketType.value === "Run Out" ? "block" : "none";
}

function toggleExtraOptions() {
  const runs = document.getElementById("runs");
  const isWicket = document.getElementById("is_wicket");
  isWicket.disabled = runs.value < 0;
  if (isWicket.disabled) {
    isWicket.checked = false;
  }
  toggleWicketType();
}

window.onload = function () {
  toggleExtraOptions();
  toggleWicketType();
};

let team1Count = 2;
let team2Count = 2;

function addPlayer(team) {
  const playersDiv = document.getElementById(`${team}-players`);
  const count = team === "team1" ? ++team1Count : ++team2Count;
  const newPlayer = document.createElement("div");
  newPlayer.className = "player-input";
  newPlayer.innerHTML = `<input type="text" name="${team}" placeholder="Player ${count}">`;
  playersDiv.appendChild(newPlayer);
}

function performToss() {
  const coin = document.getElementById("coin");
  coin.classList.add("coin-flip");
  fetch("/perform_toss")
    .then((response) => response.json())
    .then((data) => {
      setTimeout(() => {
        coin.classList.remove("coin-flip");
        document.getElementById("winner").textContent = data.winner;
        coin.style.display = "none";
        document.getElementById("toss-button").style.display = "none";
        document.getElementById("toss-result").style.display = "flex";
      }, 1000);
    });
}

function switchStrike() {
  // Submit a form to switch striker and non-striker
  document.getElementById("switchStrikeForm").submit();
}

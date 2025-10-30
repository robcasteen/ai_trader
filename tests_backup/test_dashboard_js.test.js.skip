/**
 * Dashboard JavaScript tests
 */

describe("Trade Filtering", () => {
  let loadAllTradesTab;

  beforeEach(() => {
    // Fresh require before each test
    jest.resetModules();
    const dashboard = require("../src/static/js/dashboard.js");
    loadAllTradesTab = dashboard.loadAllTradesTab;

    // Set up fresh DOM with PROPER table structure
    document.body.innerHTML = `
    <span id="all-trade-count">0</span>
    <table>
      <tbody id="all-trades"></tbody>
    </table>
  `;
  });

  test("loadAllTradesTab should fetch and display all BUY/SELL trades", async () => {
    // Mock fetch to return sample trades
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () =>
          Promise.resolve([
            {
              action: "buy",
              symbol: "BTCUSD",
              timestamp: "2025-10-17T12:00:00",
              price: 100000,
              amount: 0.001,
              value: 100,
            },
            {
              action: "sell",
              symbol: "ETHUSD",
              timestamp: "2025-10-17T12:01:00",
              price: 3000,
              amount: 0.1,
              value: 300,
            },
            {
              action: "buy",
              symbol: "SOLUSD",
              timestamp: "2025-10-17T12:02:00",
              price: 200,
              amount: 1,
              value: 200,
            },
          ]),
      })
    );

    // Debug: What's in document.body?
    console.log("BEFORE:", document.body.innerHTML);

    // Verify elements exist
    const el = document.getElementById("all-trades");
    console.log("ELEMENT:", el);
    console.log("AFTER:", document.body.innerHTML);

    expect(el).not.toBeNull();

    // Run function
    await loadAllTradesTab();

    // Assertions
    expect(document.getElementById("all-trade-count").textContent).toBe("3");

    const tableBody = document.getElementById("all-trades");
    expect(tableBody).not.toBeNull();
    expect(tableBody.innerHTML).toContain("<tr>");
  });

  test("all-trade-count should match number of BUY/SELL trades", async () => {
    // ... keep existing test content
  });
});

describe("Trade Modal", () => {
  test("openAllTradesModal should load all trades", async () => {
    // Test implementation
  });
});

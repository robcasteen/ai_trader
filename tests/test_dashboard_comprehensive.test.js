/**
 * @jest-environment jsdom
 */

const fs = require("fs");
const path = require("path");

// Load the dashboard.js file
const dashboardJS = fs.readFileSync(
  path.join(__dirname, "../src/static/js/dashboard.js"),
  "utf8"
);

describe("Dashboard Core Functions", () => {
  beforeEach(() => {
    // Setup basic DOM
    document.body.innerHTML = `
      <div id="feedModal" class="feed-modal">
        <div class="feed-modal-content">
          <input type="text" id="feedModalName" />
          <input type="text" id="feedModalUrl" />
          <input type="text" id="feedModalDesc" />
        </div>
      </div>
      <div id="feeds-table"></div>
    `;

    // Mock globals
    global.alert = jest.fn();
    global.confirm = jest.fn();
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      })
    );
    global.loadStatus = jest.fn();

    // Execute dashboard.js
    eval(dashboardJS);

    // Clear initialization calls
    global.fetch.mockClear();
    global.loadStatus.mockClear();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe("Function Availability", () => {
    test("feed management functions should be defined", () => {
      expect(typeof window.editFeed).toBe("function");
      expect(typeof window.toggleFeed).toBe("function");
      expect(typeof window.testFeed).toBe("function");
      expect(typeof window.loadFeedsDetailed).toBe("function");
      expect(typeof window.showAddFeedModal).toBe("function");
      expect(typeof window.closeAddFeedModal).toBe("function");
      expect(typeof window.addNewFeed).toBe("function");
      expect(typeof window.deleteFeed).toBe("function");
      expect(typeof window.openFeedModal).toBe("function");
      expect(typeof window.closeFeedModal).toBe("function");
      expect(typeof window.saveFeedModal).toBe("function");
    });
  });

  describe("API Integration", () => {
    test("loadFeedsDetailed should fetch feeds from API", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [] }),
      });

      await window.loadFeedsDetailed();

      expect(global.fetch).toHaveBeenCalledWith("/api/feeds");
    });

    test("loadFeedsDetailed should handle API errors", async () => {
      global.fetch.mockRejectedValueOnce(new Error("Network error"));

      // Should not throw
      await expect(window.loadFeedsDetailed()).resolves.not.toThrow();
    });
  });

  describe("Error Handling", () => {
    test("dashboard should handle malformed API responses", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => null,
      });

      // Should not crash
      await expect(window.loadFeedsDetailed()).resolves.not.toThrow();
    });

    test("dashboard should handle network failures gracefully", async () => {
      global.fetch.mockRejectedValueOnce(new Error("Connection refused"));

      await expect(window.loadFeedsDetailed()).resolves.not.toThrow();
    });
  });

  describe("Modal Interaction", () => {
    test("modal should open and close", () => {
      window.openFeedModal(1, "Test", "https://test.com", "Desc");
      
      const modal = document.getElementById("feedModal");
      expect(modal.classList.contains("active")).toBe(true);

      window.closeFeedModal();
      expect(modal.classList.contains("active")).toBe(false);
    });
  });
});
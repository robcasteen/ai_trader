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

describe("Feed Management Functions", () => {
  beforeEach(() => {
    // Setup DOM
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

    // Mock globals BEFORE eval
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

    // Clear only fetch/loadStatus, NOT alert/confirm
    global.fetch.mockClear();
    global.loadStatus.mockClear();
  });

  afterEach(() => {
    // Don't use clearAllMocks - it breaks alert/confirm
    // Just clear fetch
    if (global.fetch && global.fetch.mockClear) {
      global.fetch.mockClear();
    }
  });

  describe("Modal Functions", () => {
    test("openFeedModal should populate modal fields", () => {
      window.openFeedModal(
        1,
        "Test Feed",
        "https://test.com/rss",
        "Test description"
      );

      expect(document.getElementById("feedModalName").value).toBe("Test Feed");
      expect(document.getElementById("feedModalUrl").value).toBe(
        "https://test.com/rss"
      );
      expect(document.getElementById("feedModalDesc").value).toBe(
        "Test description"
      );
      expect(
        document.getElementById("feedModal").classList.contains("active")
      ).toBe(true);
    });

    test("closeFeedModal should clear active class", () => {
      document.getElementById("feedModal").classList.add("active");
      window.closeFeedModal();

      expect(
        document.getElementById("feedModal").classList.contains("active")
      ).toBe(false);
    });

    test("saveFeedModal should validate required fields", async () => {
      document.getElementById("feedModalName").value = "";
      document.getElementById("feedModalUrl").value = "";

      await window.saveFeedModal();

      expect(global.alert).toHaveBeenCalledWith("Name and URL are required");
      expect(global.fetch).not.toHaveBeenCalled();
    });

    test("saveFeedModal should call API with correct data", async () => {
      window.openFeedModal(5, "Old Feed", "https://old.com/rss", "Old desc");

      document.getElementById("feedModalName").value = "Updated Feed";
      document.getElementById("feedModalUrl").value = "https://updated.com/rss";
      document.getElementById("feedModalDesc").value = "Updated desc";

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [] }),
      });

      await window.saveFeedModal();

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/feeds/5",
        expect.objectContaining({
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: "Updated Feed",
            url: "https://updated.com/rss",
            description: "Updated desc",
          }),
        })
      );
    });
  });

  describe("Toggle Feed", () => {
    test("toggleFeed should call toggle endpoint", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, active: false }),
      });

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [] }),
      });

      await window.toggleFeed(3);

      expect(global.fetch).toHaveBeenCalledWith("/api/feeds/3/toggle", {
        method: "PUT",
      });

      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(global.fetch).toHaveBeenNthCalledWith(2, "/api/feeds");
    });

    test("toggleFeed should handle errors gracefully", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
      });

      await window.toggleFeed(3);

      expect(global.alert).toHaveBeenCalledWith("Failed to toggle feed");
    });
  });

  describe("Delete Feed", () => {
    test("deleteFeed should confirm before deleting", async () => {
      global.confirm.mockReturnValueOnce(false);

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [{ id: 1, name: "Test" }] }),
      });

      await window.deleteFeed(1);

      expect(global.confirm).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledTimes(1);
      expect(global.fetch).toHaveBeenCalledWith("/api/feeds");
    });

    test("deleteFeed should call DELETE endpoint when confirmed", async () => {
      global.confirm.mockReturnValueOnce(true);

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [{ id: 2, name: "Test Feed" }] }),
      });

      global.fetch.mockResolvedValueOnce({
        ok: true,
      });

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [] }),
      });

      await window.deleteFeed(2);

      expect(global.fetch).toHaveBeenCalledWith("/api/feeds/2", {
        method: "DELETE",
      });

      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
  });

  describe("Edit Feed", () => {
    test("editFeed should fetch feed data and open modal", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          feeds: [
            {
              id: 7,
              name: "Existing Feed",
              url: "https://existing.com/rss",
              description: "Existing description",
            },
          ],
        }),
      });

      await window.editFeed(7);

      expect(document.getElementById("feedModalName").value).toBe(
        "Existing Feed"
      );
      expect(document.getElementById("feedModalUrl").value).toBe(
        "https://existing.com/rss"
      );
      expect(document.getElementById("feedModalDesc").value).toBe(
        "Existing description"
      );
      expect(
        document.getElementById("feedModal").classList.contains("active")
      ).toBe(true);
    });

    test("editFeed should handle missing feed", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feeds: [] }),
      });

      await window.editFeed(999);

      expect(global.alert).toHaveBeenCalledWith("Feed not found");
    });
  });

  describe("Test Feed", () => {
    test("testFeed should exist as a function", () => {
      expect(typeof window.testFeed).toBe("function");
    });

    test("testFeed should call TEST endpoint with feed ID", async () => {
      const feedId = 10;

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "success",
          entries: 42,
          title: "Test Feed Title",
          message: "Feed OK - 42 entries found",
        }),
      });

      await window.testFeed(feedId);

      expect(global.fetch).toHaveBeenCalledWith("/api/feeds/10/test", {
        method: "POST",
      });

      expect(global.alert).toHaveBeenCalledWith(
        expect.stringContaining("Entries found:")
      );
    });

    test("testFeed should handle feed errors", async () => {
      const feedId = 11;

      global.fetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          status: "error",
          error: "Invalid feed format",
        }),
      });

      await window.testFeed(feedId);

      expect(global.alert).toHaveBeenCalledWith(
        expect.stringContaining("Invalid feed format")
      );
    });

    test("testFeed should handle feed errors", async () => {
      const feedId = 11;

      const callCountBefore = global.alert.mock.calls.length;

      global.fetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          status: "error",
          error: "Invalid feed format",
        }),
      });

      await window.testFeed(feedId);

      // Check that a new alert call was made
      expect(global.alert.mock.calls.length).toBeGreaterThan(callCountBefore);

      // Check the most recent alert call
      const lastCall =
        global.alert.mock.calls[global.alert.mock.calls.length - 1][0];
      expect(lastCall).toContain("Invalid feed format");
    });
  });
});

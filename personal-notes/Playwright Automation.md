<!-- markdownlint-disable-file -->

# Playwright Automation

- Playwright is a modern alternative testing tool for Selenium and Cypress. One of the standout features of Playwright is its speed and cross browser support. It is rapidly gaining community support and supports Python and Javascript languages along with Chrome and Firefox browsers(which is what I am focussed on), so it is mature enough to get started.
- The main need for Playwright is to write automation testcases and then use these testcases(which are simply steps to follow in an app for testing as tools for an MCP server so that AI can simulate users for rapid productivity).
- A good tutorial for Playwright on youtube is https://www.youtube.com/watch?v=788GvvcfwTY&list=PLUeDIlio4THE9S6U7CUHObba0vtKXIwKP.
- Playwright needs Nodejs and VSCode installed. Install "Playwright Test for VSCode" extension aswell.
- After installing extension, open Command Pallette(Ctrl+Shift+P) and "Install Playwright". This should download and install various tools including browsers on your terminal/bash. We are good to go once we get the msg "Happy hacking"

- Once we get "Happy hacking" msg, VSCode generates the starter files: `tests/example.spec.ts` and `tests-examples/demo-todo-app.spec.ts`.
- `tests/example.spec.ts` file is meant to verify Playwright setup after installation by testing a live, static public site (https://playwright.dev/) to ensure:
  - Playwright can launch the bundled browser (Chromium, Firefox)
  - Network traffic and DNS resolution work
  - The test runner and assertions are hooked up properly
- `demo-todo-app.spec.ts` file tests a demo TODOMVC app(a basic TODO app) across CRUD operations (Create, Read, Update, Delete), routing, and state persistence.
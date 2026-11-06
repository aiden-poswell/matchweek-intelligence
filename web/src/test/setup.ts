import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// App.test.tsx renders a real 760-fixture dataset through the full app; under
// full-suite load the default 1000ms waitFor timeout can be shorter than a genuine
// render+effect flush for a 380-row list, independently of Vitest's own testTimeout.
configure({ asyncUtilTimeout: 10000 });

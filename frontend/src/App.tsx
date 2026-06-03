// Top-level client-side page switch between the paper list and reader view.

import { useState } from "react";
import HomePage from "./pages/HomePage";
import ReaderPage from "./pages/ReaderPage";

// Choose between the home page and reader page without using a router.
export default function App() {
  const [page, setPage] = useState<"home" | "reader">("home");
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);

  function openReader(paperId: number) {
    setSelectedPaperId(paperId);
    setPage("reader");
  }

  function goHome() {
    setPage("home");
  }

  return (
    <>
      {page === "home" ? (
        <HomePage onOpenReader={openReader} />
      ) : selectedPaperId !== null ? (
        <ReaderPage paperId={selectedPaperId} onBack={goHome} />
      ) : null}
    </>
  );
}
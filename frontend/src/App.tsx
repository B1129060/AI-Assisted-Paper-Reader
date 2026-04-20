import { useState } from "react";
import HomePage from "./pages/HomePage";
import ReaderPage from "./pages/ReaderPage";

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
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getFavorites,
  getPinned,
  getRecentPages,
  getRecentSymbols,
  isFavorite,
  isPinned,
  pushRecentPage,
  pushRecentSymbol,
  toggleFavorite,
  togglePinned,
  type NavMemoryItem,
} from "@/lib/workspace/nav-memory";

export function useNavMemory() {
  const [favorites, setFavorites] = useState<NavMemoryItem[]>([]);
  const [pinned, setPinned] = useState<NavMemoryItem[]>([]);
  const [recent, setRecent] = useState<NavMemoryItem[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(() => {
    setFavorites(getFavorites());
    setPinned(getPinned());
    setRecent(getRecentPages());
    setSymbols(getRecentSymbols());
  }, []);

  useEffect(() => {
    refresh();
    setReady(true);
  }, [refresh]);

  return {
    ready,
    favorites,
    pinned,
    recent,
    symbols,
    refresh,
    isFavorite,
    isPinned,
    toggleFavorite: (item: Omit<NavMemoryItem, "at">) => {
      const next = toggleFavorite(item);
      setFavorites(next);
      return next;
    },
    togglePinned: (item: Omit<NavMemoryItem, "at">) => {
      const next = togglePinned(item);
      setPinned(next);
      return next;
    },
    recordPage: (item: Omit<NavMemoryItem, "at">) => {
      const next = pushRecentPage(item);
      setRecent(next);
      return next;
    },
    recordSymbol: (symbol: string) => {
      const next = pushRecentSymbol(symbol);
      setSymbols(next);
      return next;
    },
  };
}

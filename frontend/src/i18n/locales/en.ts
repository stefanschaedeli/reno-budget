/**
 * English shadow catalogue. Per project decision (de-CH primary, no
 * English visible to users) this re-exports the German catalogue so the
 * type contract is identical and `t()` calls never crash on a missing
 * key during development. Replace with translated strings if/when the
 * project ever ships an English UI.
 */
import { de } from "./de";

export const en = de;

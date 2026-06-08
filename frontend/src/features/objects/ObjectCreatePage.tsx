import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { createObject } from "./api";
import { type ObjectCreateInput, objectCreateSchema, type ObjectType, type UnitInput } from "./types";
import { UnitEditor } from "./UnitEditor";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";

/**
 * Wizard for creating a new object. Owner-by-construction: the backend
 * automatically issues the calling user an OWNER membership on success.
 */
export function ObjectCreatePage(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [yearBuilt, setYearBuilt] = useState<string>("");
  const [type, setType] = useState<ObjectType>("mfh");
  const [units, setUnits] = useState<UnitInput[]>([
    { label: "EG", wertquote_permille: 500, area_m2: null },
    { label: "OG", wertquote_permille: 500, area_m2: null },
  ]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Switching to SFH collapses to the implicit single 1000‰ unit; the
  // backend would reject anything else, so we keep the UI honest.
  const onTypeChange = (next: ObjectType) => {
    setType(next);
    if (next === "sfh") {
      setUnits([{ label: t("objects.units.implicitLabel"), wertquote_permille: 1000, area_m2: null }]);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const payload: ObjectCreateInput = {
      name,
      address: address || null,
      year_built: yearBuilt ? Number(yearBuilt) : null,
      type,
      planning_horizon_years: 30,
      units,
    };
    const parsed = objectCreateSchema.safeParse(payload);
    if (!parsed.success) {
      setError(parsed.error.issues.map((i) => i.message).join("; "));
      return;
    }

    setBusy(true);
    try {
      const created = await createObject(parsed.data);
      navigate(`/objekte/${created.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageContainer width="narrow">
      <PageHeader title={t("objects.create.title")} />
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <label className="block">
          <span className="text-sm">{t("objects.fields.name")}</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>

        <label className="block">
          <span className="text-sm">{t("objects.fields.address")}</span>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>

        <label className="block">
          <span className="text-sm">{t("objects.fields.yearBuilt")}</span>
          <input
            type="number"
            value={yearBuilt}
            onChange={(e) => setYearBuilt(e.target.value)}
            className="mt-1 w-32 rounded border border-slate-300 px-2 py-1"
          />
        </label>

        <fieldset>
          <legend className="text-sm">{t("objects.fields.type")}</legend>
          <label className="mr-4">
            <input
              type="radio"
              name="type"
              checked={type === "sfh"}
              onChange={() => onTypeChange("sfh")}
            />{" "}
            {t("objects.type.sfh")}
          </label>
          <label>
            <input
              type="radio"
              name="type"
              checked={type === "mfh"}
              onChange={() => onTypeChange("mfh")}
            />{" "}
            {t("objects.type.mfh")}
          </label>
        </fieldset>

        <section>
          <h3 className="mb-2 text-lg font-medium">{t("objects.units.title")}</h3>
          <UnitEditor units={units} onChange={setUnits} readonly={type === "sfh"} />
        </section>

        {error && <p className="text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? t("common.submitting") : t("objects.create.submit")}
        </button>
      </form>
    </PageContainer>
  );
}

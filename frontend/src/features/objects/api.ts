/**
 * Typed API client for the objects domain.
 *
 * Every mutating call passes ``withCsrf: true`` because the backend's
 * :func:`require_csrf` dependency rejects state-changing requests that lack
 * the double-submit header.
 */
import { apiRequest } from "@/api/client";
import {
  type ObjectCreateInput,
  type ObjectDetail,
  type ObjectPublic,
  type Unit,
  type UnitInput,
  objectDetailSchema,
  objectPublicSchema,
  unitSchema,
} from "./types";

export async function listObjects(): Promise<ObjectPublic[]> {
  const raw = await apiRequest<unknown[]>("/objects");
  return raw.map((o) => objectPublicSchema.parse(o));
}

export async function getObject(id: string): Promise<ObjectDetail> {
  const raw = await apiRequest<unknown>(`/objects/${id}`);
  return objectDetailSchema.parse(raw);
}

export async function createObject(payload: ObjectCreateInput): Promise<ObjectDetail> {
  const raw = await apiRequest<unknown>("/objects", {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return objectDetailSchema.parse(raw);
}

export async function replaceUnits(
  objectId: string,
  units: UnitInput[],
): Promise<Unit[]> {
  const raw = await apiRequest<unknown[]>(`/objects/${objectId}/units`, {
    method: "PUT",
    json: units,
    withCsrf: true,
  });
  return raw.map((u) => unitSchema.parse(u));
}

export async function deleteObject(objectId: string): Promise<void> {
  await apiRequest<void>(`/objects/${objectId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

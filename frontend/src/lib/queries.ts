import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Department } from "./types";

export const useDepartments = () =>
  useQuery({
    queryKey: ["departments"],
    queryFn: () => api.get<{ items: Department[]; unassigned_devices: number }>("/departments"),
    staleTime: 60_000,
  });

export const useDeviceTypes = () =>
  useQuery({
    queryKey: ["device-types"],
    queryFn: () => api.get<{ id: number; code: string; name: string }[]>("/devices/meta/types"),
    staleTime: Infinity,
  });

import apiClient from "./api";
import { MyPermissions } from "@/types/role";

export const rolesService = {
  getMyPermissions: () =>
    apiClient.get<MyPermissions>("/roles/my-permissions").then((r) => r.data),
};

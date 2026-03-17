export interface ThirdPartyCategoryResponse {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  parent_name: string | null;
  behavior_type: string;
  is_active: boolean;
  organization_id: string;
  created_at: string;
  updated_at: string;
}

export interface ThirdPartyCategoryCreate {
  name: string;
  description?: string | null;
  parent_id?: string | null;
  behavior_type?: string;
}

export interface ThirdPartyCategoryUpdate {
  name?: string;
  description?: string | null;
  parent_id?: string | null;
  behavior_type?: string;
  is_active?: boolean;
}

export interface ThirdPartyCategoryFlat {
  id: string;
  name: string;
  display_name: string;
  parent_id: string | null;
  behavior_type: string;
  is_active: boolean;
}

export interface ThirdPartyCategoryFlatResponse {
  items: ThirdPartyCategoryFlat[];
}

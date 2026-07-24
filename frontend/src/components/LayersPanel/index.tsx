"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, Box, CheckCircle2, Database, Layers3, LoaderCircle, Pencil,
  PlusCircle, RefreshCw, Save, Search, ShieldCheck, Trash2, WandSparkles,
  Workflow, X,
} from "lucide-react";
import {
  activateTycheLayer,
  createLayer,
  deleteLayer,
  fetchCubesAutocompleteOptions,
  generateLayerMetadata,
  getLayers,
  getMqsLayers,
  updateLayer,
} from "@/services/catalogService";
import type {
  CatalogLayer,
  CubesAutocompleteOption,
  FlapiParameterDefinition,
  CubesQueryMode,
  FlapiResourceType,
  RemoteMqsLayer,
} from "@/types/catalog";
import type { GeoJSONMultiPolygon } from "@/types/geo-query";
import CubesParametersFieldset from "./CubesParametersFieldset";
import PackageParametersFieldset from "./PackageParametersFieldset";

interface LayersPanelProps {
  onClose: () => void;
  drawnSampleBoundary: GeoJSONMultiPolygon | null;
  viewportSampleBoundary: GeoJSONMultiPolygon;
}

type LayersSection = "catalog" | "new" | "mqs" | "cube" | "flow" | "tyche";
type LayerFormSection = Exclude<LayersSection, "catalog" | "mqs">;

const LAYERS_SECTIONS = [
  { id: "catalog" as const, label: "קטלוג שכבות", description: "חיפוש ועריכת שכבות", icon: Layers3 },
  { id: "new" as const, label: "שכבה חדשה", description: "חיבור מקור נתונים ידני", icon: PlusCircle },
  { id: "mqs" as const, label: "מאגר MQS", description: "ייבוא שכבות ממוריה", icon: Database },
  { id: "cube" as const, label: "FLAPI Cube", description: "קובייה ופרמטרים דינמיים", icon: Box },
  { id: "flow" as const, label: "Flow Package", description: "חבילת תהליך מ־FLAPI", icon: Workflow },
  { id: "tyche" as const, label: "שכבת Tyche", description: "מקורות מיקום וכוחותינו", icon: ShieldCheck },
];

function mergeTags(current: string[], value: string, limit: number): string[] {
  const additions = value.split(",").map((tag) => tag.trim()).filter(Boolean);
  const seen = new Set(current.map((tag) => tag.toLocaleLowerCase()));
  return [...current, ...additions.filter((tag) => {
    const key = tag.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  })].slice(0, limit);
}

function isGeometryParameter(definition: FlapiParameterDefinition): boolean {
  return [definition.name, definition.type, definition.ontology_type]
    .join(" ")
    .toLowerCase()
    .match(/geometry|polygon|wkt/) !== null;
}

function layerErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message.trim()) return fallback;
  const normalized = error.message.toLowerCase();
  if (normalized.includes("not found") || normalized.includes("(404)")) {
    return `${fallback} (404)`;
  }
  if (
    normalized.includes("unauthorized")
    || normalized.includes("forbidden")
    || normalized.includes("(401)")
    || normalized.includes("(403)")
  ) {
    return "אין הרשאה לבצע את הפעולה. בדקו את פרטי החיבור בהגדרות.";
  }
  return error.message;
}

/**
 * Catalog browser: every data layer the agent can query, searchable by
 * name / description / tags — so users know what they can ask about.
 */
export default function LayersPanel({
  onClose,
  drawnSampleBoundary,
  viewportSampleBoundary,
}: LayersPanelProps) {
  const [activeSection, setActiveSection] = useState<LayersSection>("catalog");
  const [draftSection, setDraftSection] = useState<LayerFormSection>("new");
  const [layers, setLayers] = useState<CatalogLayer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  const [provider, setProvider] = useState("mqs");
  const [sourceUrl, setSourceUrl] = useState("");
  const [tycheGeometryField, setTycheGeometryField] = useState("geometry");
  const [tycheGeoQueryField, setTycheGeoQueryField] = useState("location");
  const [tycheTimeField, setTycheTimeField] = useState("eventTime");
  const [tycheEntityField, setTycheEntityField] = useState("");
  const [displayField, setDisplayField] = useState("");
  const [profiles, setProfiles] = useState("");
  const [flapiResourceType, setFlapiResourceType] =
    useState<FlapiResourceType>("cube");
  const [packageQuery, setPackageQuery] = useState("");
  const [cubesQueryMode, setCubesQueryMode] = useState<CubesQueryMode>("auto");
  const [dynamicParameterNames, setDynamicParameterNames] = useState<string[]>([]);
  const [parameterDefinitions, setParameterDefinitions] =
    useState<FlapiParameterDefinition[]>([]);
  const [manualDynamicParameterNames, setManualDynamicParameterNames] = useState<string[]>([]);
  const [dynamicParameterOptions, setDynamicParameterOptions] =
    useState<Record<string, CubesAutocompleteOption[]>>({});
  const [dynamicParameterValues, setDynamicParameterValues] =
    useState<Record<string, string>>({});
  const [requiresSamplePolygon, setRequiresSamplePolygon] = useState(false);
  const [cubesSampleBoundary, setCubesSampleBoundary] =
    useState<GeoJSONMultiPolygon | null>(null);
  const [cubesSampleBoundarySource, setCubesSampleBoundarySource] =
    useState<"drawn" | "viewport" | null>(null);
  const [loadingDynamicParameter, setLoadingDynamicParameter] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generatingMetadata, setGeneratingMetadata] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [activatingTyche, setActivatingTyche] = useState(false);
  const [tycheMessage, setTycheMessage] = useState<string | null>(null);
  const [mqsLayers, setMqsLayers] = useState<RemoteMqsLayer[] | null>(null);
  const [mqsLoading, setMqsLoading] = useState(false);
  const [mqsSearch, setMqsSearch] = useState("");
  const [mqsMessage, setMqsMessage] = useState<string | null>(null);
  const [mqsError, setMqsError] = useState(false);
  const [editingLayerId, setEditingLayerId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editEntityField, setEditEntityField] = useState("");
  const [editDisplayField, setEditDisplayField] = useState("");
  const [editProfiles, setEditProfiles] = useState("");
  const [editTagDraft, setEditTagDraft] = useState("");
  const [editMessage, setEditMessage] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [deletingLayerId, setDeletingLayerId] = useState<string | null>(null);
  const providerName = provider.trim().toLowerCase();
  const isFlowPackage = providerName === "flapi" && flapiResourceType === "package";
  const isCubeResource = providerName === "cubes"
    || (providerName === "flapi" && flapiResourceType === "cube");
  const tycheFieldsConfigured = providerName !== "tyche" || Boolean(
    tycheGeometryField.trim()
    && tycheGeoQueryField.trim()
    && tycheTimeField.trim()
  );

  useEffect(() => {
    getLayers()
      .then((data) => setLayers(data.layers))
      .catch((err) => {
        console.error("Layer loading failed", err);
        setError(layerErrorMessage(err, "לא ניתן לטעון את קטלוג השכבות."));
      });
  }, []);

  const filtered = useMemo(() => {
    if (!layers) return [];
    const needle = search.trim().toLowerCase();
    if (!needle) return layers;
    return layers.filter((layer) =>
      [layer.name, layer.description, ...layer.tags]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [layers, search]);

  const filteredMqs = useMemo(() => {
    if (!mqsLayers) return [];
    const needle = mqsSearch.trim().toLocaleLowerCase();
    if (!needle) return mqsLayers;
    return mqsLayers.filter((layer) =>
      [layer.name, layer.description, ...layer.tags].join(" ").toLocaleLowerCase().includes(needle)
    );
  }, [mqsLayers, mqsSearch]);

  const commitTags = (value: string) => {
    setTags((current) => mergeTags(current, value, 20));
    setTagDraft("");
  };

  const removeTag = (tagToRemove: string) => {
    setTags((current) => current.filter((tag) => tag !== tagToRemove));
  };

  const startEditing = (layer: CatalogLayer) => {
    setEditingLayerId(layer.id);
    setEditName(layer.name);
    setEditDescription(layer.description);
    setEditTags(layer.tags);
    setEditEntityField(layer.entity_field ?? "");
    setEditDisplayField(layer.display_field ?? "");
    setEditProfiles(layer.profiles.join(", "));
    setEditTagDraft("");
    setEditMessage(null);
  };

  const cancelEditing = () => {
    setEditingLayerId(null);
    setEditMessage(null);
    setEditTagDraft("");
  };

  const commitEditTags = (value: string) => {
    setEditTags((current) => mergeTags(current, value, 40));
    setEditTagDraft("");
  };

  const handleSaveEdit = async () => {
    if (!editingLayerId || !editName.trim() || editSaving) return;
    const finalTags = mergeTags(editTags, editTagDraft, 40);
    setEditSaving(true);
    setEditMessage(null);
    try {
      const updated = await updateLayer(editingLayerId, {
        name: editName.trim(), description: editDescription.trim(), tags: finalTags,
        entity_field: editEntityField.trim() || null,
        display_field: editDisplayField.trim() || null,
        profiles: editProfiles.split(",").map((item) => item.trim()).filter(Boolean),
      });
      setLayers((current) => (current ?? []).map(
        (layer) => layer.id === updated.id ? updated : layer
      ));
      setEditingLayerId(null);
    } catch (err) {
      console.error("Catalog layer update failed", err);
      setEditMessage(layerErrorMessage(err, "עדכון השכבה נכשל."));
    } finally {
      setEditSaving(false);
    }
  };

  const handleDeleteLayer = async (layer: CatalogLayer) => {
    if (editSaving || deletingLayerId) return;
    const confirmed = window.confirm(
      `למחוק את השכבה ״${layer.name}״?\n\n`
      + "השכבה תוסר מהקטלוג ולא תהיה זמינה לסוכן. לא ניתן לבטל פעולה זו."
    );
    if (!confirmed) return;
    setDeletingLayerId(layer.id);
    setEditMessage(null);
    try {
      await deleteLayer(layer.id);
      setLayers((current) => (current ?? []).filter(
        (item) => item.id !== layer.id
      ));
      cancelEditing();
    } catch (err) {
      console.error("Catalog layer deletion failed", err);
      setEditMessage(layerErrorMessage(err, "מחיקת השכבה נכשלה."));
    } finally {
      setDeletingLayerId(null);
    }
  };

  const handleAddLayer = async () => {
    if (!name.trim() || !sourceUrl.trim() || saving) return;
    setSaving(true);
    setFormMessage(null);
    try {
      const created = await createLayer({
        name: name.trim(),
        description: description.trim(),
        tags,
        provider: provider.trim(),
        source_url: sourceUrl.trim(),
        flapi_resource_type: flapiResourceType,
        cubes_query_mode: cubesQueryMode,
        cubes_parameters: dynamicParameterValues,
        package_parameters: isFlowPackage ? dynamicParameterValues : {},
        package_query: isFlowPackage ? packageQuery.trim() || null : null,
        entity_field: tycheEntityField.trim() || undefined,
        display_field: displayField.trim() || undefined,
        profiles: profiles.split(",").map((item) => item.trim()).filter(Boolean),
        tyche_geometry_field: tycheGeometryField.trim(),
        tyche_geo_query_field: tycheGeoQueryField.trim(),
        tyche_time_field: tycheTimeField.trim(),
        tyche_entity_field: tycheEntityField.trim() || undefined,
      });
      setLayers((current) => [...(current ?? []), created]);
      setName("");
      setDescription("");
      setTags([]);
      setTagDraft("");
      setSourceUrl("");
      setTycheGeometryField("geometry");
      setTycheGeoQueryField("location");
      setTycheTimeField("eventTime");
      setTycheEntityField("");
      setDisplayField("");
      setProfiles("");
      setFlapiResourceType("cube");
      setPackageQuery("");
      setCubesQueryMode("auto");
      setDynamicParameterNames([]);
      setParameterDefinitions([]);
      setManualDynamicParameterNames([]);
      setDynamicParameterOptions({});
      setDynamicParameterValues({});
      setRequiresSamplePolygon(false);
      setCubesSampleBoundary(null);
      setCubesSampleBoundarySource(null);
      setFormMessage("השכבה נוספה לקטלוג בהצלחה.");
    } catch (err) {
      console.error("Layer creation failed", err);
      setFormMessage(layerErrorMessage(err, "לא ניתן להוסיף את השכבה."));
    } finally {
      setSaving(false);
    }
  };

  const handleBrowseMqs = async () => {
    setActiveSection("mqs");
    if (mqsLayers || mqsLoading) return;
    setMqsLoading(true);
    setMqsMessage(null);
    setMqsError(false);
    try {
      const result = await getMqsLayers();
      setMqsLayers(result.layers);
      if (result.skipped) setMqsMessage(`${result.skipped} רשומות לא תקינות דולגו`);
    } catch (err) {
      console.error("MQS layer browsing failed", err);
      setMqsError(true);
      setMqsMessage(layerErrorMessage(err, "טעינת שכבות MQS נכשלה."));
    } finally {
      setMqsLoading(false);
    }
  };

  const loadDynamicParameterOptions = async (
    cubeSource: string,
    parameterNames: string[],
  ) => {
    let optionsError: string | null = null;
    for (const parameterName of parameterNames) {
      setLoadingDynamicParameter(parameterName);
      try {
        const result = await fetchCubesAutocompleteOptions({
          source_url: cubeSource,
          parameter_name: parameterName,
        });
        setDynamicParameterOptions((current) => ({
          ...current,
          [parameterName]: result.options,
        }));
      } catch (err) {
        console.error(`Cubes ${parameterName} autocomplete fetch failed`, err);
        optionsError = layerErrorMessage(
          err,
          `טעינת אפשרויות ${parameterName} נכשלה.`,
        );
      } finally {
        setLoadingDynamicParameter(null);
      }
    }
    if (optionsError) {
      setFormMessage(`${optionsError} — אפשר לנסות לטעון שוב.`);
    }
  };

  const handleGenerateMetadata = async (
    selected?: RemoteMqsLayer,
    selectedDynamicValues: Record<string, string> = dynamicParameterValues,
    selectedBoundary: GeoJSONMultiPolygon | null = cubesSampleBoundary,
  ) => {
    const target = {
      name: selected?.name ?? name,
      provider: selected?.provider ?? provider,
      source_url: selected?.source_url ?? sourceUrl,
      flapi_resource_type: flapiResourceType,
      cubes_query_mode: cubesQueryMode,
      cubes_parameters: selectedDynamicValues,
      package_parameters: isFlowPackage ? selectedDynamicValues : {},
      package_query: isFlowPackage ? packageQuery.trim() || null : null,
      cubes_sample_boundary: selectedBoundary,
      tyche_geometry_field: tycheGeometryField.trim(),
      tyche_geo_query_field: tycheGeoQueryField.trim(),
      tyche_time_field: tycheTimeField.trim(),
      tyche_entity_field: tycheEntityField.trim() || undefined,
    };
    if (!target.name.trim() || !target.provider.trim() || !target.source_url.trim()) return;
    setGeneratingMetadata(true);
    setFormMessage("דוגם עד 10 ישויות ומייצר תיאור ותגיות…");
    try {
      const generated = await generateLayerMetadata(target);
      setRequiresSamplePolygon(generated.requires_sample_polygon);
      if (generated.sample_count > 0) {
        setDescription(generated.description);
        setTags(generated.tags);
        setTagDraft("");
      }
      const definitions = [...generated.configurable_parameters];
      for (const manualName of manualDynamicParameterNames) {
        if (!definitions.some(
          (item) => item.name.toLocaleLowerCase() === manualName.toLocaleLowerCase()
        )) {
          definitions.push({
            name: manualName,
            display_name: "",
            description: "",
            type: "string",
            required: true,
            single_value: true,
            ontology_type: "",
            has_default: false,
            dynamic: true,
            options: [],
          });
        }
      }
      const parameterNames = definitions.map((item) => item.name);
      setParameterDefinitions(definitions);
      setDynamicParameterNames(parameterNames);
      setDynamicParameterOptions((current) => Object.fromEntries(
        definitions
          .map((item) => {
            const staticOptions = item.options.map((value) => ({ value, name: value }));
            return [
              item.name,
              item.dynamic
                ? current[item.name]
                : staticOptions.length > 0 ? staticOptions : undefined,
            ] as const;
          })
          .filter((entry): entry is readonly [string, CubesAutocompleteOption[]] =>
            Boolean(entry[1])
          )
      ));
      setDynamicParameterValues((current) => Object.fromEntries(
        parameterNames
          .filter((parameterName) => current[parameterName])
          .map((parameterName) => [parameterName, current[parameterName]])
      ));
      const missingParameters = definitions.some(
        (definition) =>
          definition.required
          && !definition.has_default
          && !isGeometryParameter(definition)
          && !selectedDynamicValues[definition.name]
      );
      const missingPolygon = generated.requires_sample_polygon && !selectedBoundary;
      setFormMessage(
        missingParameters && missingPolygon
          ? "יש לבחור ערכים לפרמטרים הנדרשים ופוליגון לדגימת ה-metadata."
          : missingPolygon
          ? "ה-Cube דורש פוליגון לדגימת metadata — בחרו פוליגון שצויר במפה או את תחום התצוגה."
          : missingParameters
          ? "נמצאו פרמטרים נדרשים — יש לבחור ערכים לפני טעינת התוצאות."
          : parameterNames.length > 0
          ? `נטענו ${generated.sample_count} תוצאות עבור הפרמטרים שהוגדרו ונוצרו הצעות.`
          : `נוצרו הצעות מ-${generated.sample_count} ישויות אקראיות — אפשר לערוך לפני ההוספה.`
      );
      const dynamicNames = isCubeResource ? definitions
        .filter((item) => item.dynamic)
        .map((item) => item.name) : [];
      if (dynamicNames.length > 0) {
        // Required controls are already visible. Autocomplete hydration runs
        // separately so a slow child cube cannot keep metadata generation
        // in its busy state or hide the parameters from the user.
        void loadDynamicParameterOptions(
          target.source_url.trim(), dynamicNames
        );
      }
    } catch (err) {
      console.error("Layer metadata generation failed", err);
      setFormMessage(layerErrorMessage(err, "יצירת התיאור והתגיות נכשלה."));
    } finally {
      setGeneratingMetadata(false);
    }
  };

  const handleFetchDynamicOptions = async (parameterName: string) => {
    if (!sourceUrl.trim() || loadingDynamicParameter) return;
    setLoadingDynamicParameter(parameterName);
    setFormMessage(null);
    try {
      const result = await fetchCubesAutocompleteOptions({
        source_url: sourceUrl.trim(), parameter_name: parameterName,
      });
      setDynamicParameterOptions((current) => ({ ...current, [parameterName]: result.options }));
    } catch (err) {
      console.error("Cubes autocomplete fetch failed", err);
      setFormMessage(layerErrorMessage(err, "טעינת אפשרויות הפרמטר נכשלה."));
    } finally {
      setLoadingDynamicParameter(null);
    }
  };

  const handleSelectDynamicParameter = (parameterName: string, value: string) => {
    const selectedDynamicValues = {
      ...dynamicParameterValues,
      [parameterName]: value,
    };
    setDynamicParameterValues(selectedDynamicValues);
    const allDynamicParametersSelected = dynamicParameterNames.every(
      (parameterName) => {
        const definition = parameterDefinitions.find(
          (item) => item.name === parameterName
        );
        return !definition?.required
          || definition.has_default
          || isGeometryParameter(definition)
          || Boolean(selectedDynamicValues[parameterName]);
      }
    );
    if (allDynamicParametersSelected && (!requiresSamplePolygon || cubesSampleBoundary)) {
      void handleGenerateMetadata(undefined, selectedDynamicValues);
    } else if (requiresSamplePolygon && !cubesSampleBoundary) {
      setFormMessage("יש לבחור פוליגון לדגימת ה-metadata.");
    } else {
      setFormMessage("יש לבחור ערך לכל הפרמטרים הנדרשים.");
    }
  };

  const handleUseSampleBoundary = (
    boundary: GeoJSONMultiPolygon,
    source: "drawn" | "viewport",
  ) => {
    setCubesSampleBoundary(boundary);
    setCubesSampleBoundarySource(source);
    const allParametersSelected = dynamicParameterNames.every(
      (parameterName) => {
        const definition = parameterDefinitions.find(
          (item) => item.name === parameterName
        );
        return !definition?.required
          || definition.has_default
          || isGeometryParameter(definition)
          || Boolean(dynamicParameterValues[parameterName]);
      }
    );
    if (allParametersSelected) {
      void handleGenerateMetadata(undefined, dynamicParameterValues, boundary);
    } else {
      setFormMessage("הפוליגון נבחר. כעת יש לבחור ערך לכל הפרמטרים הנדרשים.");
    }
  };

  const handleAddDynamicParameter = (parameterName: string): boolean => {
    if (dynamicParameterNames.some(
      (name) => name.toLocaleLowerCase() === parameterName.toLocaleLowerCase()
    )) {
      setFormMessage(`הפרמטר ${parameterName} כבר נוסף.`);
      return false;
    }
    setManualDynamicParameterNames((current) => [...current, parameterName]);
    setDynamicParameterNames((current) => [...current, parameterName]);
    setParameterDefinitions((current) => [...current, {
      name: parameterName,
      display_name: "",
      description: "",
      type: "string",
      required: true,
      single_value: true,
      ontology_type: "",
      has_default: false,
      dynamic: true,
      options: [],
    }]);
    if (sourceUrl.trim()) {
      void handleFetchDynamicOptions(parameterName);
    } else {
      setFormMessage("יש להזין קודם שם Cube, ואז לטעון את אפשרויות הפרמטר.");
    }
    return true;
  };

  const selectMqsLayer = (layer: RemoteMqsLayer) => {
    setName(layer.name);
    setDescription(layer.description);
    setTags(layer.tags);
    setTagDraft("");
    setProvider(layer.provider);
    setSourceUrl(layer.source_url);
    setTycheGeometryField("geometry");
    setTycheGeoQueryField("location");
    setTycheTimeField("eventTime");
    setTycheEntityField("");
    setDisplayField(layer.display_field ?? "");
    setProfiles(layer.profiles?.join(", ") ?? "");
    setFlapiResourceType("cube");
    setPackageQuery("");
    setCubesQueryMode("auto");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setFormMessage(null);
    setDraftSection("new");
    setActiveSection("new");
    void handleGenerateMetadata(layer, {}, null);
  };

  const startManualLayer = () => {
    setProvider("mqs");
    setSourceUrl("");
    setTycheGeometryField("geometry");
    setTycheGeoQueryField("location");
    setTycheTimeField("eventTime");
    setTycheEntityField("");
    setDisplayField("");
    setProfiles("");
    setFlapiResourceType("cube");
    setPackageQuery("");
    setCubesQueryMode("auto");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setName("");
    setDescription("");
    setTags([]);
    setTagDraft("");
    setFormMessage("הזינו את פרטי המקור והמטא־דאטה של השכבה.");
    setDraftSection("new");
    setActiveSection("new");
  };

  const startCubesLayer = () => {
    setProvider("flapi");
    setFlapiResourceType("cube");
    setPackageQuery("");
    setSourceUrl("");
    setTycheGeometryField("geometry");
    setTycheGeoQueryField("location");
    setTycheTimeField("eventTime");
    setTycheEntityField("");
    setDisplayField("");
    setProfiles("");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setName("");
    setDescription("");
    setTags([]);
    setTagDraft("");
    setCubesQueryMode("auto");
    setFormMessage("הזינו שם שכבה ושם Cube, ואז הפעילו יצירת תיאור ותגיות.");
    setDraftSection("cube");
    setActiveSection("cube");
  };

  const startFlowPackage = () => {
    setProvider("flapi");
    setFlapiResourceType("package");
    setPackageQuery("");
    setSourceUrl("");
    setTycheGeometryField("geometry");
    setTycheGeoQueryField("location");
    setTycheTimeField("eventTime");
    setTycheEntityField("");
    setDisplayField("");
    setProfiles("");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setName("");
    setDescription("");
    setTags([]);
    setTagDraft("");
    setFormMessage(
      "הזינו שם ו-ID של Flow Package, ואז טענו את הגדרות הפרמטרים."
    );
    setDraftSection("flow");
    setActiveSection("flow");
  };

  const startTycheLayer = () => {
    setProvider("tyche");
    setSourceUrl("");
    setTycheGeometryField("geometry");
    setTycheGeoQueryField("location");
    setTycheTimeField("eventTime");
    setTycheEntityField("");
    setDisplayField("");
    setProfiles("");
    setFlapiResourceType("cube");
    setPackageQuery("");
    setCubesQueryMode("auto");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setName("");
    setDescription("");
    setTags([]);
    setTagDraft("");
    setFormMessage(
      "הזינו שם, נתיב API ושמות שדות; אפשר לדגום את השכבה לפני השמירה."
    );
    setDraftSection("tyche");
    setActiveSection("tyche");
  };

  const selectSection = (section: LayersSection) => {
    if (section === "catalog") {
      setActiveSection("catalog");
    } else if (section === "mqs") {
      void handleBrowseMqs();
    } else if (section === draftSection) {
      setActiveSection(section);
    } else if (section === "new") {
      startManualLayer();
    } else if (section === "cube") {
      startCubesLayer();
    } else if (section === "flow") {
      startFlowPackage();
    } else {
      startTycheLayer();
    }
  };

  const handleActivateTyche = async () => {
    if (activatingTyche) return;
    setActivatingTyche(true);
    setTycheMessage("בודק חיבור ל-Tyche ומפעיל את השכבה…");
    try {
      const activated = await activateTycheLayer();
      setLayers((current) => {
        const remaining = (current ?? []).filter((item) => item.id !== activated.id);
        return [...remaining, activated];
      });
      setTycheMessage("שכבת כוחותינו פעילה בקטלוג.");
    } catch (err) {
      console.error("Tyche layer activation failed", err);
      setTycheMessage(layerErrorMessage(err, "הפעלת Tyche נכשלה."));
    } finally {
      setActivatingTyche(false);
    }
  };

  const activeSectionConfig = LAYERS_SECTIONS.find(({ id }) => id === activeSection)
    ?? LAYERS_SECTIONS[0];
  const ActiveSectionIcon = activeSectionConfig.icon;
  const isFormSection = activeSection !== "catalog" && activeSection !== "mqs";

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div
        className="settings-card layers-card layers-workspace-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="layers-title"
      >
        <header className="settings-header layers-workspace-header">
          <div className="settings-title">
            <span className="settings-title-icon"><Layers3 size={20} /></span>
            <div>
              <h2 id="layers-title">ניהול שכבות</h2>
              <p>קטלוג מקורות המידע שהסוכן יכול לחפש ולנתח</p>
            </div>
          </div>
          <div className="layers-header-actions">
            <span className={`layers-count${error ? " bad" : ""}`}>
              {error ? <AlertTriangle size={14} /> : <Layers3 size={14} />}
              {error ? "לא זמין" : layers ? `${layers.length} שכבות` : "טוען…"}
            </span>
            <button type="button" className="settings-close" onClick={onClose} aria-label="סגירת ניהול שכבות">
              <X size={20} />
            </button>
          </div>
        </header>

        <div className="layers-workspace-layout">
          <nav className="layers-nav" aria-label="קטגוריות ניהול שכבות">
            <p className="settings-nav-label">קטגוריות</p>
            {LAYERS_SECTIONS.map(({ id, label, description, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={activeSection === id ? "active" : ""}
                onClick={() => selectSection(id)}
                aria-current={activeSection === id ? "page" : undefined}
              >
                <Icon size={18} />
                <span>
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
              </button>
            ))}
            <div className={`layers-connection ${error ? "bad" : layers ? "ok" : "loading"}`}>
              {error
                ? <AlertTriangle size={17} />
                : layers
                  ? <CheckCircle2 size={17} />
                  : <LoaderCircle className="submit-spinner" size={17} />}
              <span>
                <strong>{error ? "הקטלוג לא זמין" : layers ? "הקטלוג מחובר" : "מתחבר לקטלוג"}</strong>
                <small>{error ? "בדקו את חיבור מסד הנתונים" : layers ? `${layers.length} שכבות זמינות` : "טוען נתונים…"}</small>
              </span>
            </div>
          </nav>

          <main className="layers-content">
            <div className="layers-section-heading">
              <span><ActiveSectionIcon size={19} /></span>
              <div>
                <h3>{activeSectionConfig.label}</h3>
                <p>{activeSectionConfig.description}</p>
              </div>
            </div>

            {activeSection === "mqs" && (
              <section className="mqs-browser layers-section" aria-label="בחירת שכבת MQS">
                <div className="layers-search">
                  <Search size={17} />
                  <input
                    value={mqsSearch}
                    onChange={(e) => setMqsSearch(e.target.value)}
                    placeholder="חיפוש במאגר MQS…"
                    aria-label="חיפוש במאגר MQS"
                    dir="auto"
                  />
                </div>
                {mqsLoading && (
                  <div className="layers-state" role="status">
                    <LoaderCircle className="submit-spinner" size={18} />
                    <span>שכבות MQS נטענות…</span>
                  </div>
                )}
                {mqsMessage && (
                  <div className={`layers-state ${mqsError ? "error" : "info"}`} role={mqsError ? "alert" : "status"} dir="auto">
                    <AlertTriangle size={18} />
                    <span>{mqsMessage}</span>
                  </div>
                )}
                <ul className="mqs-picker-list">
                  {filteredMqs.map((layer) => (
                    <li key={layer.id}>
                      <button type="button" className="mqs-picker-item" onClick={() => selectMqsLayer(layer)}>
                        <span className="mqs-picker-icon"><PlusCircle size={17} /></span>
                        <span>
                          <strong dir="auto">{layer.name}</strong>
                          {layer.description && <span dir="auto">{layer.description}</span>}
                          <small dir="auto">{layer.tags.join(" · ")}</small>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                {mqsLayers !== null && filteredMqs.length === 0 && (
                  <div className="layers-empty-state">
                    <Search size={22} />
                    <strong>לא נמצאו שכבות מתאימות</strong>
                    <p>נסו חיפוש קצר יותר או מונח אחר.</p>
                  </div>
                )}
              </section>
            )}

            {isFormSection && (
              <section className="add-layer-form layers-section" aria-label="הוספת שכבה לקטלוג">
                {activeSection === "tyche" && (
                  <div className="tyche-activation-card">
                    <span><ShieldCheck size={20} /></span>
                    <div>
                      <strong>שכבת כוחותינו המובנית</strong>
                      <small>בדיקת החיבור והפעלה מיידית בקטלוג</small>
                    </div>
                    <button
                      type="button"
                      className="catalog-edit-button"
                      onClick={() => void handleActivateTyche()}
                      disabled={activatingTyche}
                    >
                      {activatingTyche
                        ? <LoaderCircle className="submit-spinner" size={15} />
                        : <RefreshCw size={15} />}
                      {activatingTyche ? "מפעיל…" : "הפעלה"}
                    </button>
                  </div>
                )}
                {tycheMessage && activeSection === "tyche" && (
                  <div className="layers-state info" role="status" dir="auto">
                    <CheckCircle2 size={18} />
                    <span>{tycheMessage}</span>
                  </div>
                )}
            <div className="settings-input-row">
              <div>
                <label className="field-label" htmlFor="layer-name">שם</label>
                <input id="layer-name" className="settings-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="בתי ספר" dir="auto" />
              </div>
              <div>
                <label className="field-label" htmlFor="layer-provider">ספק</label>
                <input
                  id="layer-provider"
                  className="settings-input"
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value);
                    setTycheGeometryField("geometry");
                    setTycheGeoQueryField("location");
                    setTycheTimeField("eventTime");
                    setTycheEntityField("");
                    setDisplayField("");
                    setProfiles("");
                    setFlapiResourceType("cube");
                    setPackageQuery("");
                    setDynamicParameterNames([]);
                    setParameterDefinitions([]);
                    setManualDynamicParameterNames([]);
                    setDynamicParameterOptions({});
                    setDynamicParameterValues({});
                    setRequiresSamplePolygon(false);
                    setCubesSampleBoundary(null);
                    setCubesSampleBoundarySource(null);
                  }}
                  placeholder="mqs"
                  dir="ltr"
                />
              </div>
            </div>
            <label className="field-label" htmlFor="layer-description">תיאור</label>
            <textarea id="layer-description" className="settings-input layer-description-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="איזה מידע גיאוגרפי השכבה מכילה" dir="auto" />
            <label className="field-label" htmlFor="layer-tags">תגיות <span className="optional">(Enter או פסיק להוספה)</span></label>
            <div className="tag-editor" onClick={() => document.getElementById("layer-tags")?.focus()}>
              {tags.map((tag) => (
                <span key={tag} className="tag-editor-chip" dir="auto">
                  {tag}
                  <button type="button" onClick={(e) => { e.stopPropagation(); removeTag(tag); }} aria-label={`הסרת התגית ${tag}`}>
                    <X size={13} />
                  </button>
                </span>
              ))}
              <input
                id="layer-tags"
                className="tag-editor-input"
                value={tagDraft}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value.includes(",")) commitTags(value);
                  else setTagDraft(value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    commitTags(tagDraft);
                  } else if (e.key === "Backspace" && !tagDraft && tags.length > 0) {
                    removeTag(tags[tags.length - 1]);
                  }
                }}
                onBlur={() => commitTags(tagDraft)}
                placeholder={tags.length === 0 ? "חינוך, בית ספר, ילדים" : "תגית נוספת…"}
                dir="auto"
              />
            </div>
            <label className="field-label" htmlFor="layer-entity-field">
              שדה מזהה ישות יציב <span className="optional">(אופציונלי)</span>
            </label>
            <input
              id="layer-entity-field"
              className="settings-input"
              value={tycheEntityField}
              onChange={(event) => setTycheEntityField(event.target.value)}
              placeholder="entityId"
              dir="ltr"
            />
            <div className="settings-input-row">
              <div>
                <label className="field-label" htmlFor="layer-display-field">
                  שדה תצוגה <span className="optional">(אופציונלי)</span>
                </label>
                <input
                  id="layer-display-field"
                  className="settings-input"
                  value={displayField}
                  onChange={(event) => setDisplayField(event.target.value)}
                  placeholder="displayName"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="field-label" htmlFor="layer-profiles">
                  Profiles <span className="optional">(מופרדים בפסיק)</span>
                </label>
                <input
                  id="layer-profiles"
                  className="settings-input"
                  value={profiles}
                  onChange={(event) => setProfiles(event.target.value)}
                  placeholder="friends"
                  dir="ltr"
                />
              </div>
            </div>
            <label className="field-label" htmlFor="layer-source-url">
              {isFlowPackage
                ? "Flow Package ID"
                : isCubeResource
                ? "שם Cube / database"
                : providerName === "tyche"
                  ? "נתיב Tyche"
                  : "כתובת המקור"}
            </label>
            <input
              id="layer-source-url"
              className="settings-input"
              value={sourceUrl}
              onChange={(e) => {
                setSourceUrl(e.target.value);
                setRequiresSamplePolygon(false);
                setCubesSampleBoundary(null);
                setCubesSampleBoundarySource(null);
              }}
              placeholder={
                isFlowPackage
                  ? "466192 (or flapi://package/466192)"
                  : isCubeResource
                    ? "transport (or flapi://cube/transport)"
                    : providerName === "tyche"
                      ? "alerts (או /coordinate/v1/alerts)"
                      : "https://provider.example/layer"
              }
              dir="ltr"
            />
            {providerName === "tyche" && (
              <fieldset className="cubes-query-mode">
                <legend>מיפוי שדות Tyche</legend>
                <div className="settings-input-row">
                  <div>
                    <label className="field-label" htmlFor="tyche-geometry-field">
                      שדה גאומטריה בתוצאה
                    </label>
                    <input
                      id="tyche-geometry-field"
                      className="settings-input"
                      value={tycheGeometryField}
                      onChange={(event) => setTycheGeometryField(event.target.value)}
                      placeholder="geometry"
                      dir="ltr"
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="tyche-time-field">
                      שדה זמן האירוע
                    </label>
                    <input
                      id="tyche-time-field"
                      className="settings-input"
                      value={tycheTimeField}
                      onChange={(event) => setTycheTimeField(event.target.value)}
                      placeholder="eventTime"
                      dir="ltr"
                    />
                  </div>
                </div>
                <label className="field-label" htmlFor="tyche-geo-query-field">
                  שדה הסינון הגאוגרפי בבקשה
                </label>
                <input
                  id="tyche-geo-query-field"
                  className="settings-input"
                  value={tycheGeoQueryField}
                  onChange={(event) => setTycheGeoQueryField(event.target.value)}
                  placeholder="location"
                  dir="ltr"
                />
              </fieldset>
            )}
            {isFlowPackage && (
              <>
                <label className="field-label" htmlFor="package-query">
                  תוצאת Query / Cube{" "}
                  <span className="optional">
                    (אופציונלי; ריק = השאילתות האחרונות בכל ענף)
                  </span>
                </label>
                <input
                  id="package-query"
                  className="settings-input"
                  value={packageQuery}
                  onChange={(event) => setPackageQuery(event.target.value)}
                  placeholder="FinalCubeName"
                  dir="ltr"
                />
              </>
            )}
            {isCubeResource && (
              <fieldset className="cubes-query-mode">
                <legend>מבנה שאילתת זמן וגיאוגרפיה</legend>
                <div className="cubes-query-mode-options">
                  {([
                    ["auto", "אוטומטי", "לפי ה-metadata של ה-Cube"],
                    ["match_not", "match / not", "From/To, TimeBack ו-Location"],
                    ["legacy", "Legacy", "מבנה השעה היחסית הקיים"],
                  ] as const).map(([value, title, detail]) => (
                    <button
                      key={value}
                      type="button"
                      className={cubesQueryMode === value ? "active" : ""}
                      aria-pressed={cubesQueryMode === value}
                      onClick={() => setCubesQueryMode(value)}
                    >
                      <strong dir={value === "auto" ? "rtl" : "ltr"}>{title}</strong>
                      <small>{detail}</small>
                    </button>
                  ))}
                </div>
              </fieldset>
            )}
            {isCubeResource && (
              <CubesParametersFieldset
                definitions={parameterDefinitions}
                options={dynamicParameterOptions}
                values={dynamicParameterValues}
                loadingParameter={loadingDynamicParameter}
                busy={generatingMetadata}
                sourceConfigured={Boolean(sourceUrl.trim())}
                onAddManual={handleAddDynamicParameter}
                onFetchOptions={(parameterName) => {
                  void handleFetchDynamicOptions(parameterName);
                }}
                onSelect={handleSelectDynamicParameter}
                onChangeValue={(parameterName, value) => {
                  setDynamicParameterValues((current) => ({
                    ...current,
                    [parameterName]: value,
                  }));
                }}
              />
            )}
            {isFlowPackage && (
              <PackageParametersFieldset
                definitions={parameterDefinitions}
                values={dynamicParameterValues}
                busy={generatingMetadata}
                onChange={(parameterName, value) => {
                  setDynamicParameterValues((current) => ({
                    ...current,
                    [parameterName]: value,
                  }));
                }}
              />
            )}
            {requiresSamplePolygon && (
              <fieldset className="cubes-query-mode cubes-sample-polygon">
                <legend>פוליגון לדגימת metadata</legend>
                <div className="cubes-query-mode-options cubes-sample-polygon-options">
                  <button
                    type="button"
                    className={cubesSampleBoundarySource === "drawn" ? "active" : ""}
                    aria-pressed={cubesSampleBoundarySource === "drawn"}
                    disabled={!drawnSampleBoundary || generatingMetadata}
                    onClick={() => {
                      if (drawnSampleBoundary) {
                        handleUseSampleBoundary(drawnSampleBoundary, "drawn");
                      }
                    }}
                  >
                    <strong>שימוש בפוליגון שצויר</strong>
                    <small>{drawnSampleBoundary ? "פוליגון/מלבן הקיים במפה" : "סגרו, ציירו פוליגון ופתחו שוב"}</small>
                  </button>
                  <button
                    type="button"
                    className={cubesSampleBoundarySource === "viewport" ? "active" : ""}
                    aria-pressed={cubesSampleBoundarySource === "viewport"}
                    disabled={generatingMetadata}
                    onClick={() => handleUseSampleBoundary(
                      viewportSampleBoundary, "viewport"
                    )}
                  >
                    <strong>שימוש בתחום התצוגה</strong>
                    <small>האזור שמוצג כרגע במפה</small>
                  </button>
                </div>
              </fieldset>
            )}
            <div className="layers-form-actions">
              {formMessage && <p className="settings-message" role="status" dir="auto">{formMessage}</p>}
              <button
                type="button"
                className="layers-metadata-button"
                onClick={() => void handleGenerateMetadata()}
                disabled={
                  !name.trim() || !provider.trim() || !sourceUrl.trim()
                  || !tycheFieldsConfigured || generatingMetadata
                }
              >
                {generatingMetadata
                  ? <LoaderCircle className="submit-spinner" size={16} />
                  : <WandSparkles size={16} />}
                {generatingMetadata ? "מייצר מטא־דאטה…" : "יצירת תיאור ותגיות"}
              </button>
              <button
                type="button"
                className="run-query-button layers-save-button"
                onClick={handleAddLayer}
                disabled={
                  !name.trim() || !sourceUrl.trim() || !tycheFieldsConfigured || saving ||
                  parameterDefinitions.some(
                    (definition) =>
                      definition.required
                      && !definition.has_default
                      && !isGeometryParameter(definition)
                      && !dynamicParameterValues[definition.name]
                  )
                }
              >
                {saving
                  ? <LoaderCircle className="submit-spinner" size={16} />
                  : <Save size={16} />}
                {saving ? "מוסיף…" : "הוספת שכבה"}
              </button>
            </div>
          </section>
        )}

        {activeSection === "catalog" && (
          <section className="layers-section layers-catalog-section" aria-label="קטלוג שכבות">
            <div className="layers-catalog-toolbar">
              <div className="layers-search">
                <Search size={17} />
                <input
                  placeholder="חיפוש לפי שם, תגית או תיאור…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="חיפוש בקטלוג השכבות"
                  dir="auto"
                />
              </div>
              {layers && <span>{filtered.length} מתוך {layers.length}</span>}
            </div>
            {error && (
              <div className="layers-state error" role="alert" dir="auto">
                <AlertTriangle size={19} />
                <span>{error}</span>
              </div>
            )}
            {layers === null && !error && (
              <div className="layers-state" role="status">
                <LoaderCircle className="submit-spinner" size={19} />
                <span>השכבות נטענות…</span>
              </div>
            )}

            <ul className="layers-list">
          {filtered.map((layer) => (
            <li key={layer.id} className="layers-item" dir="auto">
              <div className="layers-item-head">
                <span className="layers-item-name">{layer.name}</span>
                {editingLayerId !== layer.id && (
                  <button
                    type="button"
                    className="catalog-edit-button"
                    onClick={() => startEditing(layer)}
                    aria-label={`עריכת השכבה ${layer.name}`}
                  >
                    <Pencil size={14} />
                    עריכה
                  </button>
                )}
              </div>
              {editingLayerId === layer.id ? (
                <div className="catalog-edit-form">
                  <label className="field-label" htmlFor={`edit-name-${layer.id}`}>שם</label>
                  <input
                    id={`edit-name-${layer.id}`}
                    className="settings-input"
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    dir="auto"
                  />
                  <label className="field-label" htmlFor={`edit-description-${layer.id}`}>תיאור</label>
                  <textarea
                    id={`edit-description-${layer.id}`}
                    className="settings-input layer-description-input"
                    value={editDescription}
                    onChange={(event) => setEditDescription(event.target.value)}
                    dir="auto"
                  />
                  <label className="field-label" htmlFor={`edit-tags-${layer.id}`}>תגיות</label>
                  <div className="tag-editor">
                    {editTags.map((tag) => (
                      <span key={tag} className="tag-editor-chip" dir="auto">
                        {tag}
                        <button
                          type="button"
                          onClick={() => setEditTags((current) => current.filter((item) => item !== tag))}
                          aria-label={`הסרת התגית ${tag}`}
                        ><X size={13} /></button>
                      </span>
                    ))}
                    <input
                      id={`edit-tags-${layer.id}`}
                      className="tag-editor-input"
                      value={editTagDraft}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (value.includes(",")) commitEditTags(value);
                        else setEditTagDraft(value);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                          event.preventDefault();
                          commitEditTags(editTagDraft);
                        } else if (event.key === "Backspace" && !editTagDraft && editTags.length > 0) {
                          setEditTags((current) => current.slice(0, -1));
                        }
                      }}
                      onBlur={() => commitEditTags(editTagDraft)}
                      placeholder="תגית נוספת…"
                      dir="auto"
                    />
                  </div>
                  <div className="settings-input-row">
                    <div>
                      <label className="field-label" htmlFor={`edit-entity-${layer.id}`}>
                        שדה מזהה ישות
                      </label>
                      <input
                        id={`edit-entity-${layer.id}`}
                        className="settings-input"
                        value={editEntityField}
                        onChange={(event) => setEditEntityField(event.target.value)}
                        dir="ltr"
                      />
                    </div>
                    <div>
                      <label className="field-label" htmlFor={`edit-display-${layer.id}`}>
                        שדה תצוגה
                      </label>
                      <input
                        id={`edit-display-${layer.id}`}
                        className="settings-input"
                        value={editDisplayField}
                        onChange={(event) => setEditDisplayField(event.target.value)}
                        dir="ltr"
                      />
                    </div>
                  </div>
                  <label className="field-label" htmlFor={`edit-profiles-${layer.id}`}>
                    Profiles
                  </label>
                  <input
                    id={`edit-profiles-${layer.id}`}
                    className="settings-input"
                    value={editProfiles}
                    onChange={(event) => setEditProfiles(event.target.value)}
                    placeholder="friends, our-force"
                    dir="ltr"
                  />
                  {editMessage && (
                    <p className="settings-message" role="alert" dir="auto">
                      {editMessage}
                    </p>
                  )}
                  <div className="catalog-edit-actions">
                    <button
                      type="button"
                      className="run-query-button"
                      onClick={() => void handleSaveEdit()}
                      disabled={!editName.trim() || editSaving || Boolean(deletingLayerId)}
                    >
                      {editSaving
                        ? <LoaderCircle className="submit-spinner" size={15} />
                        : <Save size={15} />}
                      {editSaving ? "שומר…" : "שמירה"}
                    </button>
                    <button
                      type="button"
                      className="catalog-edit-button"
                      onClick={cancelEditing}
                      disabled={editSaving || Boolean(deletingLayerId)}
                    >
                      ביטול
                    </button>
                    <button
                      type="button"
                      className="catalog-delete-button"
                      onClick={() => void handleDeleteLayer(layer)}
                      disabled={editSaving || Boolean(deletingLayerId)}
                      aria-label={`מחיקת השכבה ${layer.name}`}
                    >
                      {deletingLayerId === layer.id
                        ? <LoaderCircle className="submit-spinner" size={15} />
                        : <Trash2 size={15} />}
                      {deletingLayerId === layer.id ? "מוחק…" : "מחיקת שכבה"}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {layer.description && (
                    <p className="layers-item-description">{layer.description}</p>
                  )}
                  {layer.tags.length > 0 && (
                    <div className="layers-item-tags">
                      {layer.tags.slice(0, 6).map((tag) => <span key={tag}>{tag}</span>)}
                      {layer.tags.length > 6 && <small>+{layer.tags.length - 6}</small>}
                    </div>
                  )}
                </>
              )}
            </li>
          ))}
          {layers !== null && filtered.length === 0 && (
            <li className="layers-empty-state">
              <Search size={22} />
              <strong>לא נמצאו שכבות</strong>
              <p>אין התאמה לחיפוש ״{search}״.</p>
            </li>
          )}
            </ul>
          </section>
        )}
          </main>
        </div>
      </div>
    </div>
  );
}

import Sortable from "sortablejs";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLExporter } from "three/examples/jsm/exporters/STLExporter.js";

frappe.provide("is_production");

is_production.Sortable = Sortable;
is_production.THREE = THREE;
is_production.OrbitControls = OrbitControls;
is_production.STLExporter = STLExporter;

window.Sortable = Sortable;

console.log("SortableJS loaded");
console.log("Three.js loaded", THREE.REVISION);
console.log("STLExporter loaded");
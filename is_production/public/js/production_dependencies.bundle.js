import Sortable from "sortablejs";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

frappe.provide("is_production");

is_production.Sortable = Sortable;
is_production.THREE = THREE;
is_production.OrbitControls = OrbitControls;

window.Sortable = Sortable;

console.log("SortableJS loaded");
console.log("Three.js loaded", THREE.REVISION);

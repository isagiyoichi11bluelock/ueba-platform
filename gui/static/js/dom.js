/**
 * Safe DOM creation and text escaping helpers.
 * Never inserts unescaped user data via innerHTML.
 */

export function el(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);

  for (const [key, val] of Object.entries(attrs)) {
    if (val === undefined || val === null) continue;
    if (key === "className" || key === "class") {
      element.className = val;
    } else if (key.startsWith("on") && typeof val === "function") {
      const eventName = key.slice(2).toLowerCase();
      element.addEventListener(eventName, val);
    } else if (key === "dataset") {
      for (const [dKey, dVal] of Object.entries(val)) {
        element.dataset[dKey] = dVal;
      }
    } else {
      element.setAttribute(key, val);
    }
  }

  for (const child of children) {
    if (child === undefined || child === null) continue;
    if (typeof child === "string" || typeof child === "number") {
      element.appendChild(document.createTextNode(String(child)));
    } else if (child instanceof Node) {
      element.appendChild(child);
    } else if (Array.isArray(child)) {
      for (const item of child) {
        if (item instanceof Node) element.appendChild(item);
        else if (item !== undefined && item !== null) element.appendChild(document.createTextNode(String(item)));
      }
    }
  }

  return element;
}

export function safeText(str) {
  return document.createTextNode(str === undefined || str === null ? "" : String(str));
}

export function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}


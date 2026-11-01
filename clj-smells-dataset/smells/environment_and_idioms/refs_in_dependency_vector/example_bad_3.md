## Metadata

* **Smell name:** Refs in Dependency Vector
* **Expected smell location:** Function `my-component`
* **Affected forms:** `r/use-effect`
* **Short explanation:** Passing a Reagent atom directly in a dependency vector doesn't trigger reactivity properly; it should be dereferenced.

```Clojure
(ns ui.settings
  (:require [reagent.core :as r]))

(defn settings-panel []
  (let [theme (r/atom "dark")]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Dependency vector contains an atom ref instead of its value
      (r/use-effect
       (fn [] (.setAttribute js/document.body "theme" @theme))
       [theme])
      ; VALIDATION: SMELL END
      [:div "Theme: " @theme])))
```

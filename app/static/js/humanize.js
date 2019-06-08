/* javascript lmao */
function roundTo(n, digits) {
    var negative = false;
    if (digits === undefined) {
        digits = 0;
    }
        if( n < 0) {
        negative = true;
      n = n * -1;
    }
    var multiplicator = Math.pow(10, digits);
    n = parseFloat((n * multiplicator).toFixed(11));
    n = (Math.round(n) / multiplicator).toFixed(2);
    if( negative ) {
        n = (n * -1).toFixed(2);
    }
    return n;
};

function roundToThree(num) {
    return +(Math.round(num + "e+3")  + "e-3");
}

function roundToOne(num) {
    return +(Math.round(num + "e+1")  + "e-1");
}

function fmt_quantity_small(val){
    if (val === null){return "None";}
    if (val === "N/A"){return val;}
    v = Math.abs(val);
    if(v < 0.001){return "<0.001";}
    //if (v < 1){return roundTo(val, 3);}
    if (v < 1){return +(Math.round(val + "e+3")  + "e-3");}
    if (v < 10){return +(Math.round(val + "e+2")  + "e-2");}
    if (v < 1000){return Math.floor(val);}
    if (v < 1000000){ return Math.floor(val / 1000) + " K";}
    return Math.floor(val / 1000000) + " M";
};

function fmt_quantity(val){
    if (val === null){return "None";}
    v = Math.abs(val);
    if (v < 1000){return roundTo(val, 1);}
    if (v < 10000){ return roundTo(val / 1000, 2) + " K";}
    if (v < 100000){return roundTo(val / 1000, 1) + " K";}
    if (v < 1000000){return Math.floor(val / 1000) + " K";}
    if (v < 10000000){return roundTo(val / 1000000, 2) + " M";}
    if (v < 100000000){return roundTo(val / 1000000, 1) + " M";}
    if (v < 1000000000){return Math.floor(val / 1000000) + " M";}
    if (v < 10000000000){return roundTo(val / 1000000000, 2) + " B";}
    return roundTo(val / 1000000000, 1) + " B";
};


function fmt_isk(val) {
    if (val === null){return "None";}
    if (val === "N/A"){return val;}
    v = Math.abs(val);
    if (v < 10){return roundTo(val, 2);}
    if (v < 100){return roundTo(val, 1);}
    if (v < 1000){return roundTo(val / 1000, 3) + " K";}
    if (v < 10000){ return roundTo(val / 1000, 2) + " K";}
    if (v < 100000){return roundTo(val / 1000, 1) + " K";}
    if (v < 1000000){return Math.floor(val / 1000) + " K";}
    if (v < 10000000){return roundTo(val / 1000000, 2) + " M";}
    if (v < 100000000){return roundTo(val / 1000000, 1) + " M";}
    if (v < 1000000000){return Math.floor(val / 1000000) + " M";}
    if (v < 10000000000){return roundTo(val / 1000000000, 2) + " B";}
    return roundTo(val / 1000000000, 1) + " B";
}
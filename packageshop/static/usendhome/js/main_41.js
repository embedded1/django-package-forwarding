var POSTOCDES_REGEX = {
    'AC': /^[A-Z]{4}[0-9][A-Z]$/,
    'AD': /^AD[0-9]{3}$/,
    'AF': /^[0-9]{4}$/,
    'AI': /^AI-2640$/,
    'AL': /^[0-9]{4}$/,
    'AM': /^[0-9]{4}$/,
    'AR': /^([0-9]{4}|[A-Z][0-9]{4}[A-Z]{3})$/,
    'AS': /^[0-9]{5}(-[0-9]{4}|-[0-9]{6})?$/,
    'AT': /^[0-9]{4}$/,
    'AU': /^[0-9]{4}$/,
    'AX': /^[0-9]{5}$/,
    'AZ': /^AZ[0-9]{4}$/,
    'BA': /^[0-9]{5}$/,
    'BB': /^BB[0-9]{5}$/,
    'BD': /^[0-9]{4}$/,
    'BE': /^[0-9]{4}$/,
    'BG': /^[0-9]{4}$/,
    'BH': /^[0-9]{3,4}$/,
    'BL': /^[0-9]{5}$/,
    'BM': /^[A-Z]{2}([0-9]{2}|[A-Z]{2})/,
    'BN': /^[A-Z}{2}[0-9]]{4}$/,
    'BO': /^[0-9]{4}$/,
    'BR': /^[0-9]{5}(-[0-9]{3})?$/,
    'BT': /^[0-9]{3}$/,
    'BY': /^[0-9]{6}$/,
    'CA': /^[A-Z][0-9][A-Z][0-9][A-Z][0-9]$/,
    'CC': /^[0-9]{4}$/,
    'CH': /^[0-9]{4}$/,
    'CL': /^([0-9]{7}|[0-9]{3}-[0-9]{4})$/,
    'CN': /^[0-9]{6}$/,
    'CO': /^[0-9]{6}$/,
    'CR': /^[0-9]{4,5}$/,
    'CU': /^[0-9]{5}$/,
    'CV': /^[0-9]{4}$/,
    'CX': /^[0-9]{4}$/,
    'CY': /^[0-9]{4}$/,
    'CZ': /^[0-9]{5}$/,
    'DE': /^[0-9]{5}$/,
    'DK': /^[0-9]{4}$/,
    'DO': /^[0-9]{5}$/,
    'DZ': /^[0-9]{5}$/,
    'EC': /^EC[0-9]{6}$/,
    'EE': /^[0-9]{5}$/,
    'EG': /^[0-9]{5}$/,
    'ES': /^[0-9]{5}$/,
    'ET': /^[0-9]{4}$/,
    'FI': /^[0-9]{5}$/,
    'FK': /^[A-Z]{4}[0-9][A-Z]{2}$/,
    'FM': /^[0-9]{5}(-[0-9]{4})?$/,
    'FO': /^[0-9]{3}$/,
    'FR': /^[0-9]{5}$/,
    'GA': /^[0-9]{2}.*[0-9]{2}$/,
    'GB': /^[A-Z][A-Z0-9]{1,3}[0-9][A-Z]{2}$/,
    'GE': /^[0-9]{4}$/,
    'GF': /^[0-9]{5}$/,
    'GG': /^([A-Z]{2}[0-9]{2,3}[A-Z]{2})$/,
    'GI': /^GX111AA$/,
    'GL': /^[0-9]{4}$/,
    'GP': /^[0-9]{5}$/,
    'GR': /^[0-9]{5}$/,
    'GS': /^SIQQ1ZZ$/,
    'GT': /^[0-9]{5}$/,
    'GU': /^[0-9]{5}$/,
    'GW': /^[0-9]{4}$/,
    'HM': /^[0-9]{4}$/,
    'HN': /^[0-9]{5}$/,
    'HR': /^[0-9]{5}$/,
    'HT': /^[0-9]{4}$/,
    'HU': /^[0-9]{4}$/,
    'ID': /^[0-9]{5}$/,
    'IL': /^[0-9]{7}$/,
    'IM': /^IM[0-9]{2,3}[A-Z]{2}$$/,
    'IN': /^[0-9]{6}$/,
    'IO': /^[A-Z]{4}[0-9][A-Z]{2}$/,
    'IQ': /^[0-9]{5}$/,
    'IR': /^[0-9]{5}-[0-9]{5}$/,
    'IS': /^[0-9]{3}$/,
    'IT': /^[0-9]{5}$/,
    'JE': /^JE[0-9]{2}[A-Z]{2}$/,
    'JM': /^JM[A-Z]{3}[0-9]{2}$/,
    'JO': /^[0-9]{5}$/,
    'JP': /^[0-9]{3}-?[0-9]{4}$/,
    'KE': /^[0-9]{5}$/,
    'KG': /^[0-9]{6}$/,
    'KH': /^[0-9]{5}$/,
    'KR': /^[0-9]{3}-?[0-9]{3}$/,
    'KY': /^KY[0-9]-[0-9]{4}$/,
    'KZ': /^[0-9]{6}$/,
    'LA': /^[0-9]{5}$/,
    'LB': /^[0-9]{8}$/,
    'LI': /^[0-9]{4}$/,
    'LK': /^[0-9]{5}$/,
    'LR': /^[0-9]{4}$/,
    'LS': /^[0-9]{3}$/,
    'LT': /^[0-9]{5}$/,
    'LU': /^[0-9]{4}$/,
    'LV': /^LV-[0-9]{4}$/,
    'LY': /^[0-9]{5}$/,
    'MA': /^[0-9]{5}$/,
    'MC': /^980[0-9]{2}$/,
    'MD': /^MD-?[0-9]{4}$/,
    'ME': /^[0-9]{5}$/,
    'MF': /^[0-9]{5}$/,
    'MG': /^[0-9]{3}$/,
    'MH': /^[0-9]{5}$/,
    'MK': /^[0-9]{4}$/,
    'MM': /^[0-9]{5}$/,
    'MN': /^[0-9]{5}$/,
    'MP': /^[0-9]{5}$/,
    'MQ': /^[0-9]{5}$/,
    'MT': /^[A-Z]{3}[0-9]{4}$/,
    'MV': /^[0-9]{4,5}$/,
    'MX': /^[0-9]{5}$/,
    'MY': /^[0-9]{5}$/,
    'MZ': /^[0-9]{4}$/,
    'NA': /^[0-9]{5}$/,
    'NC': /^[0-9]{5}$/,
    'NE': /^[0-9]{4}$/,
    'NF': /^[0-9]{4}$/,
    'NG': /^[0-9]{6}$/,
    'NI': /^[0-9]{3}-[0-9]{3}-[0-9]$/,
    'NL': /^[0-9]{4}[A-Z]{2}$/,
    'NO': /^[0-9]{4}$/,
    'NP': /^[0-9]{5}$/,
    'NZ': /^[0-9]{4}$/,
    'OM': /^[0-9]{3}$/,
    'PA': /^[0-9]{6}$/,
    'PE': /^[0-9]{5}$/,
    'PF': /^[0-9]{5}$/,
    'PG': /^[0-9]{3}$/,
    'PH': /^[0-9]{4}$/,
    'PK': /^[0-9]{5}$/,
    'PL': /^[0-9]{2}-?[0-9]{3}$/,
    'PM': /^[0-9]{5}$/,
    'PN': /^[A-Z]{4}[0-9][A-Z]{2}$/,
    'PR': /^[0-9]{5}$/,
    'PT': /^[0-9]{4}(-?[0-9]{3})?$/,
    'PW': /^[0-9]{5}$/,
    'PY': /^[0-9]{4}$/,
    'RE': /^[0-9]{5}$/,
    'RO': /^[0-9]{6}$/,
    'RS': /^[0-9]{5}$/,
    'RU': /^[0-9]{6}$/,
    'SA': /^[0-9]{5}$/,
    'SD': /^[0-9]{5}$/,
    'SE': /^[0-9]{5}$/,
    'SG': /^([0-9]{2}|[0-9]{4}|[0-9]{6})$/,
    'SH': /^(STHL1ZZ|TDCU1ZZ)$/,
    'SI': /^(SI-)?[0-9]{4}$/,
    'SK': /^[0-9]{5}$/,
    'SM': /^[0-9]{5}$/,
    'SN': /^[0-9]{5}$/,
    'SV': /^01101$/,
    'SZ': /^[A-Z][0-9]{3}$/,
    'TC': /^TKCA1ZZ$/,
    'TD': /^[0-9]{5}$/,
    'TH': /^[0-9]{5}$/,
    'TJ': /^[0-9]{6}$/,
    'TM': /^[0-9]{6}$/,
    'TN': /^[0-9]{4}$/,
    'TR': /^[0-9]{5}$/,
    'TT': /^[0-9]{6}$/,
    'TW': /^[0-9]{5}$/,
    'UA': /^[0-9]{5}$/,
    'US': /^[0-9]{5}(-[0-9]{4}|-[0-9]{6})?$/,
    'UY': /^[0-9]{5}$/,
    'UZ': /^[0-9]{6}$/,
    'VA': /^00120$/,
    'VC': /^VC[0-9]{4}/,
    'VE': /^[0-9]{4}[A-Z]?$/,
    'VG': /^VG[0-9]{4}$/,
    'VI': /^[0-9]{5}$/,
    'VN': /^[0-9]{6}$/,
    'WF': /^[0-9]{5}$/,
    'XK': /^[0-9]{5}$/,
    'YT': /^[0-9]{5}$/,
    'ZA': /^[0-9]{4}$/,
    'ZM': /^[0-9]{5}$/
};

var usendhome = (function(o, $) {
    o.init = function() {
        var $page_inner = $('.page_inner');

        //$('footer').prev('.page_inner').css('padding-bottom', '100px');

        $page_inner.on('click', ':checkbox[readonly]', function() {
            return false;
        });
        $page_inner.on('click', '.js-disable-on-click', function() {
            $(this).button('loading');
        });
        $page_inner.on('click', 'button.submit', function(e) {
            $(this).closest('.row').find('form').submit();
        });
        $page_inner.on('click', '.modalFormSubmit', function(e) {
            $(this).closest('.modal-content').find('form').submit();
        });
        $page_inner.on('click', '.submit_form', function(e) {
            e.preventDefault();
            $(this).prev("form").submit();
        });
        $page_inner.on('focus', 'input', function() {
            $(this).parent().find('.input-group-addon').css('color', '#3498db');

        }).on('blur', 'input', function() {
            $(this).parent().find('.input-group-addon').css('color', '#bec6cd');
        });
        $page_inner.on('focus', 'input[readonly]', function() {
            $(this).parent().find('.input-group-addon').css('color', '#bec6cd');
        }).on('blur', 'input[readonly]', function() {
            $(this).parent().find('.input-group-addon').css('color', '#bec6cd');
        });
        $page_inner.on('click', '.select2-container', function() {
            if ($(this).hasClass('select2-container-disabled')) {
                $('.select2-container-disabled').parent().find('.input-group-addon').addClass('readonly');
            }
        });
        $page_inner.on("select2-open", 'select', function() {
            $(this).closest('.input-group').find('.input-group-addon').css('color', '#3498db');
        });
        $page_inner.on("select2-focus", 'select', function() {
             $(this).closest('.input-group').find('.input-group-addon').css('color', '#3498db');
        });
        $page_inner.on("select2-open", 'select[readonly]', function() {
            $(this).closest('.input-group').find('.input-group-addon').css('color', '#bec6cd');
        });
        $page_inner.on("select2-focus", 'select[readonly]', function() {
             $(this).closest('.input-group').find('.input-group-addon').css('color', '#bec6cd');
        });
        $page_inner.on("select2-close", 'select', function() {
             $(this).closest('.input-group').find('.input-group-addon').css('color', '#bec6cd');
        });
        $page_inner.on("select2-blur", 'select', function() {
            $(this).closest('.input-group').find('.input-group-addon').css('color', '#bec6cd');
        });
        $page_inner.on("click", '.js-enable-on-checked', function() {
            var $this = $(this),
                $submit_button = $this.closest('form').find('button[type="submit"]');

            if($this.prop('checked')) {
                $submit_button.removeAttr('disabled');
            }
            else {
                $submit_button.attr('disabled', true);
            }
        });
        $page_inner.on("click", "#add-to-chrome", function() {
            chrome.webstore.install(undefined, function() {
                $.ajax({
                    type: 'POST',
                    url: "/chrome/added/"
                });
            });
        });
        /** Bootstrap Tooltip **/
        $('[data-toggle="tooltip"]').tooltip();
        /** Bootstrap Popover **/
        $('[data-toggle="popover"]').popover();
        o.register_select2();
        o.initSwitch();
        o.initModalLoad();
        //add support for placeholder for older browsers
        $('input, textarea').placeholder();
        o.initAjax();
        o.handleIE();
        analytics.ready(function(){
            var anonId = mixpanel.get_distinct_id();
            $('#id_mixpanel_anon_id').val(anonId);
        });
        if(!o.isDesktopChrome()) {
            $(".chrome").hide();
        }
        if($('#exitModal').length) {
            //show exit modal only for users who can add it to chrome
            setTimeout(function() {
                if(o.isDesktopChrome()) {
                    $("body").mouseleave(function(){ $('#exitModal').modal('show');});
                    //remove the exit modal after it shows for the first time
                    $('#exitModal').on('hidden.bs.modal', function (e) {
                        $(this).remove();
                    });
                }
            }, 3000);
        }
    };

    o.isDesktopChrome = function() {
        //check if user is on mobile
        var isMobile = 'ontouchstart' in window;
        try {
            chrome;
        }
        catch(err) {
            return false;
        }
        return true;//!isMobile;
    };

    o.getUrlVars = function() {
        var vars = {};
        var parts = window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m,key,value) {
            vars[key] = value;
        });
        return vars;
    };

    o.handleIE = function() {
        var ie = (function(){
            var undef,rv = -1; // Return value assumes failure.
            var ua = window.navigator.userAgent;
            var msie = ua.indexOf('MSIE ');
            var trident = ua.indexOf('Trident/');

            if (msie > 0) {
                // IE 10 or older => return version number
                rv = parseInt(ua.substring(msie + 5, ua.indexOf('.', msie)), 10);
            } else if (trident > 0) {
                // IE 11 (or newer) => return version number
                var rvNum = ua.indexOf('rv:');
                rv = parseInt(ua.substring(rvNum + 3, ua.indexOf('.', rvNum)), 10);
            }

            return ((rv > -1) ? rv : undef);
        }());
        if(ie > 9) {
            $('body').addClass('ie-body');
        }
    };


    o.initAjax = function() {
        function csrfSafeMethod(method) {
            // these HTTP methods do not require CSRF protection
            return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
        }
        function sameOrigin(url) {
            // test that a given url is a same-origin URL
            // url could be relative or scheme relative or absolute
            var host = document.location.host; // host + port
            var protocol = document.location.protocol;
            var sr_origin = '//' + host;
            var origin = protocol + sr_origin;
            // Allow absolute or scheme relative URLs to same origin
            return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
                (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
                // or any other URL that isn't scheme relative or absolute i.e relative.
                !(/^(\/\/|http:|https:).*/.test(url));
        }
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!csrfSafeMethod(settings.type) && sameOrigin(settings.url)) {
                    // Send the token to same-origin, relative URLs only.
                    // Send the token only if the method warrants CSRF protection
                    // Using the CSRFToken value acquired earlier
                    xhr.setRequestHeader("X-CSRFToken", o.getCsrfToken());
                }
            }
        });
    };


    o.initModalLoad = function(cb)  {
        var $page_inner = $('.page_inner');

        if (typeof cb === 'undefined') {
            cb = function (data, modal) {
                if ( data.redirect_url ) {
                    $(modal).on('hide.bs.modal', function (e) {
                        window.location = data.redirect_url;
                    });
                }
            };
        }
        else {
             $page_inner.off('click', '.modalRemoteLoad');
        }

        $page_inner.on('click', '.modalRemoteLoad', function() {
            var $this = $(this),
                load_url = $this.data('load-url'),
                modal_id = '#' + $this.data('modal-name'),
                modal_body_id = modal_id + 'Body';

            $(modal_body_id).load(load_url, function () {
                $(modal_id).on('show.bs.modal', function (e) {
                    o.register_select2();
                    o.formAjaxSubmit(modal_body_id +' form', modal_id, cb);
                });
                $(modal_id).modal('toggle');
            });
        });
    };

    o.initSwitch = function() {
        $('.page_inner').on('click', '.switch:not(.deactivate)', function(e) {
            var $this = $(this),
                $switch_animate = $this.find('.switch-animate');

            //stop event bubbling
            e.stopPropagation ? e.stopPropagation() : (e.cancelBubble=true);

            $switch_animate.toggleClass('switch-on');
            $switch_animate.toggleClass('switch-off');
            $switch_animate.find('input[type="checkbox"]').prop('checked', $switch_animate.hasClass('switch-on'));
        });
        $('.switch:not(.deactivate)').each(function(index) {
            var $this = $(this),
                $switch_animate = $this.find('.switch-animate');
            $switch_animate.find('input[type="checkbox"]').prop('checked', $switch_animate.hasClass('switch-on'));
        });
    };

    o.getCsrfToken = function() {
        var cookieValue = null,
            name = 'csrftoken';
        if (document.cookie && document.cookie != '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    o.homepage = {
        init: function () {
            $(window).scroll(function(){
                if ( ($(this).scrollTop()) >= 90 ) {
                    $("nav").addClass("navbar-mini");
                } else {
                    $("nav").removeClass("navbar-mini");
                }
            });

            analytics.ready(function(){
                if(window.location.href.indexOf('logout') > -1) {
                    analytics.reset();
                }
            });
        }
    };

    o.register = function() {
        $('.tooltip-msg').on('focus', function() {
            var $this = $(this);

            $this.tooltip('show');
            setTimeout(function($tooltip) {
                $tooltip.tooltip('destroy');
            }, 3000, $this)
        }).on('blur', function() {
                $(this).tooltip('destroy');
        });
        $("#id_country").select2({

            formatNoMatches: function (term) {
                return "Oh snap, we don't ship there";
            },
            matcher: function(term, text) {
                if(text.toUpperCase().indexOf(term.toUpperCase()) == 0) {
                    return true;
                }
                return false;
            }
        });
        $('#create-account').on('click', function(){
            $('#account-setup').submit();
        });
        $('#customized-services-modal').on('change', function() {
            $("#customized-services").val($(this).val());
        });
        $("#customized-services-item").on('click', function() {
            var $this = $(this);

            if($this.hasClass('selected')) {
                $('#customized-services-modal').val('');
                $("#customized-services").val('');
            }
            else {
                $('#customizedServicesModal').modal('show');
            }
            $this.toggleClass('selected');
        });
        $(".item[data-input-id]").on('click', function() {
            var $this = $(this),
                $input_id = $($this.data('input-id'));

            $this.toggleClass('selected');
            $input_id.prop("checked", !$input_id.prop("checked"));
        });
        $('.js-enable-on-checked').on('click', function() {
            var $submit_button = $('#create-account');
            if($(this).prop('checked')) {
                $submit_button.removeAttr('disabled');
            }
            else {
                $submit_button.attr('disabled', true);
            }
        });
        analytics.ready(function(){
            var anonId = mixpanel.get_distinct_id();
            $('#id_mixpanel_anon_id').val(anonId);
        });
        $("#extras").on('click', function() {
           $(".extras-settings").slideToggle("slow");
        });
        //analytics.ready(function(){
        //   analytics.page("Signup Page")
        //});
    };

    o.formAjaxSubmit = function(form, modal, success_cb) {
        $(form).submit(function (e) {
            var $this = $(this);
            e.preventDefault();
            $.ajax({
                type: $this.attr('method'),
                url: $this.attr('action'),
                data: $this.serialize(),
                success: function (data) {
                    if ( data.is_valid ) {
                        success_cb(data, modal);
                        $(modal).modal('toggle');
                    } else {
                        $(modal).find('.modal-body').html(data.content_html);
                        o.formAjaxSubmit(form, modal, success_cb);
                    }
                },
                error: function (xhr, ajaxOptions, thrownError) {
                    // handle response errors here
                }
            });
       });
    };

    o.initDatepicker = function () {
        // Date range
        $('#id_date_from').datepicker({
            dateFormat: 'dd.mm.yy',
            prevText: '<i class="fa fa-angle-left"></i>',
            nextText: '<i class="fa fa-angle-right"></i>'
        });
        $('#id_date_to').datepicker({
            dateFormat: 'dd.mm.yy',
            prevText: '<i class="fa fa-angle-left"></i>',
            nextText: '<i class="fa fa-angle-right"></i>'
        });
    };

    o.register_select2 = function() {
        $('select').each( function () {
            var $this = $(this),
                is_readonly = $this.is('[readonly]');
            $this.select2({
                minimumResultsForSearch: 10,
                matcher: function(term, text) {
                  if (text.toUpperCase().indexOf(term.toUpperCase()) == 0) {
                    return true;
                  }
                  return false;
                }
            });
            //$('.select2-container').css("width", "100%");
            $this.select2("readonly", is_readonly);
        });

    };

    o.messages = {
        addMessages: function(messages) {
            for (var level in messages) {
                for (var i=0; i<messages[level].length; i++) {
                    o.messages[level](messages[level][i]);
                }
            }
        },
        addMessage: function(tag, msg, icon) {
            var msgHTML = '<div class="alert fade in alert-' + tag + '">' +
                '<a href="#" class="close" data-dismiss="alert">&times;</a>'  + icon +
                ' ' + msg + '</div>';
            $('#messages').append($(msgHTML));
        },
        debug: function(msg) { o.messages.addMessage('debug', msg, '<i class=fa fa-check-circle"></i>'); },
        info: function(msg) { o.messages.addMessage('info', msg, '<i class="fa fa-info-circle"></i>'); },
        success: function(msg) { o.messages.addMessage('success', msg, '<i class="fa fa-check-circle"></i>'); },
        warning: function(msg) { o.messages.addMessage('warning', msg, '<i class="fa fa-warning"></i>'); },
        error: function(msg) { o.messages.addMessage('danger', msg, '<i class="fa fa-exclamation-circle"></i>'); }
    };

    o.isotope = {
        addressBookInit: function() {
            // Initialize Isotope plugin for filtering
            var $container = $('.addresses_container');

            $container.isotope({
                itemSelector : '.address-book-item'
            });

            // filter items when filter link is clicked
            $(".filter-buttons").on('click', 'button', function() {
                $(this).parent().find('button').removeClass("active");
                $(this).addClass("active");
                var filterValue = $(this).data('filter');
                $container.isotope({filter: filterValue});
            });
        },
        shippingMethodsInit: function() {
            // Initialize Isotope plugin for sorting
            var $container = $('.shipping_methods_container');

            $container.imagesLoaded( function(){
                $container.isotope({
                    itemSelector : '.shipping-method',
                    getSortData : {
                        delivery : function($elem){
                            return parseInt($elem.data('delivery'), 10);
                        },
                        rate : function($elem){
                            return parseFloat($elem.data('rate'));
                        }
                    }
                });
            });

            // filter items when filter link is clicked
            $(".sort-by").on('click', 'a', function() {
                var $this = $(this),
                     selector = $this.data('filter');
                $this.parent().find('a').removeClass("active");
                $this.addClass("active");
                $container.isotope({sortBy: selector});
            });
        }
    };

    o.task = {
        handleShippingMethodsResults: function(data) {
            var $search_results = $('.search-results'),
                $button = $("button[type='submit']");
            //reset search button
            if($button) {
                $button.button('reset');
            }
            //insert new data
            if(data.content_html){
                //$search_results.addClass('white-row');
                $search_results.html(data.content_html).fadeIn('slow');
            }
            //init isotope
            o.isotope.shippingMethodsInit();
            o.initSwitch();
            //$('#messages').html('');
            o.messages.addMessages(data.messages);
            o.spinner.stopSpinner();

        },
        handleShippingMethodsResultsFailure: function(data) {
            var $button = $("button[type='submit']");
            //reset search button
            if($button) {
                $button.button('reset');
            }
             $('#messages').html('');
            o.messages.addMessages(data.messages);
            o.spinner.stopSpinner();
        },
        handle_celery_task_status: function(data, task_id, status_url, success_cb, failure_cb) {
            switch(data.status) {
                case 'RUNNING':
                    // check status in 1 second
                    setTimeout(function() {
                        $.ajax({
                            type: 'GET',
                            url: status_url,
                            data: {'task_id': task_id},
                            success: function(data) {
                                task_id = data.task_id ? data.task_id : task_id;
                                o.task.handle_celery_task_status(data, task_id, status_url, success_cb, failure_cb);
                            },
                            dataType:'json'
                        });
                    }, 1000);
                    break;
                case 'COMPLETED':
                    success_cb(data);
                    break;
                default:
                    failure_cb(data);
            }
        }
    };

    o.calculator = {
        init: function() {
            var $dimensions_units = $('#id_dimension_units'),
                $weight_units     = $('#id_weight_units');
            //$('.page_inner').css('min-height', '95vh');
            //Init spinner
            o.spinner.initSpinner();
            o.calculator.initValidation();
            $('.calc-select-75 input')
                .focus(function() {
                    $('.calc-select-75 input').addClass('focus');
                    $('.calc-select-75 .input-group-addon').addClass('focus');
                    $('.calc-select-25 .select2-choice').addClass('focus');

                })
                .blur(function() {
                    $('.calc-select-75 input').removeClass('focus');
                    $('.calc-select-75 .input-group-addon').removeClass('focus');
                    $('.calc-select-25 .select2-choice').removeClass('focus');
                });

            $('.calc-select-60 input')
                .focus(function() {
                    $('.calc-select-40 .select2-choice').addClass('focus');
                })
                .blur(function() {
                    $('.calc-select-40 .select2-choice').removeClass('focus');
                });

            $dimensions_units.on("select2-open, select2-focus", function() {
                $('.calc-select-75 input').addClass('focus');
                $('.calc-select-75 .input-group-addon').addClass('focus');
                $('.calc-select-25 .select2-choice').addClass('focus');
            });

            $dimensions_units.on("select2-close, select2-blur", function() {
                $('.calc-select-75 input').removeClass('focus');
                $('.calc-select-75 .input-group-addon').removeClass('focus');
                $('.calc-select-25 .select2-choice').removeClass('focus');
            });

            $weight_units.on("select2-open, select2-focus", function() {
                $('.calc-select-60 input').addClass('focus');
                $('.calc-select-60 .input-group-addon').addClass('focus');
                $('.calc-select-40 .select2-choice').addClass('focus');
            });

            $weight_units.on("select2-close, select2-blur", function() {
                $('.calc-select-60 input').removeClass('focus');
                $('.calc-select-60 .input-group-addon').removeClass('focus');
                $('.calc-select-40 .select2-choice').removeClass('focus');
            });
        },
        submitShippingMethodsSearch: function($form) {
            var payload = $form.serialize();
            $.ajax({
                type: 'POST',
                url: $form.attr("action"),
                data: payload,
                beforeSend: function() {
                    $('.search-results').hide().html('');
                    $('#messages').html('');
                    o.spinner.startSpinner();
                },
                success: function(data) {
                    if(data.is_valid){
                        o.task.handle_celery_task_status(data, data.task_id, data.status_url,
                            o.task.handleShippingMethodsResults,
                            o.task.handleShippingMethodsResultsFailure);
                    }
                    else{
                        $form.html(data.content_html);
                        o.register_select2();
                       //re validate form
                        $form.data('bootstrapValidator').destroy();
                        o.calculator.initValidation();
                    }
                },
                dataType:'json'
            });
        },
        formSubmit: function($form) {
            //add disable-on-click class to the submit button
            //to prevent form submit until we return with the shipping methods
            var $button = $("button[type='submit']");
            $button.button('loading');
            $button.trigger('blur');
            o.calculator.submitShippingMethodsSearch($form);
        },
        initValidation: function() {
	        $("#amazon-calc")
                .find('[name="country"]')
                    .select2({
                        formatNoMatches: function (term) {
                            return "Oh snap, we don't ship there";
                        },
                        matcher: function(term, text) {
                            if(text.toUpperCase().indexOf(term.toUpperCase()) == 0) {
                                return true;
                            }
                            return false;
                        }
                    })
                    // Revalidate the color when it is changed
                    .change(function(e) {
                        var $amazon_calc = $('#amazon-calc');
                        $amazon_calc.bootstrapValidator('revalidateField', 'country');
                        $amazon_calc.bootstrapValidator('revalidateField', 'postcode');
                    })
                    .end()
                .bootstrapValidator({
                    container: '#calculator-messages',
                    excluded: [':disabled', "#id_city"],
                    verbose: false,
                    fields: {
                        country: {
                            validators: {
                                callback: {
                                    message: 'The destination country is required',
                                    callback: function(value, validator, $field) {
                                        return value.length > 0;
                                    }
                                }
                            }
                        },
                        postcode: {
                            validators: {
                                callback: {
                                    callback: function(value, validator, $field) {
                                        var country_code = validator.getFieldElements('country').val(),
                                            country_regex = POSTOCDES_REGEX[country_code];

                                        if(value !== '' && country_code !== '') {
                                            return true;
                                        }else if(value === '' && country_code !== '') {
                                            if(country_regex === undefined) {
                                                return true;
                                            }else {
                                                return {
                                                    valid: false,
                                                    message: 'The postal code is required'
                                                }
                                            }
                                        }
                                        else {
                                            return true;
                                        }
                                    }
                                }
                            }
                        },
                        product_url: {
                            validators: {
                                notEmpty: {
                                    message: 'The Amazon product url is required'
                                },
                                regexp: {
                                    regexp: /^(http|https):\/\/www.amazon.com\/+/i,
                                    message: 'Only Amazon.com product URL supported'
                                },
                                uri: {
                                    message: 'The Amazon product url is invalid'
                                }
                            }
                        }
                    }
	        }).on('success.form.bv', function(e) {
                // Prevent form submission
                e.preventDefault();
                // Get the form instance
                var $form = $(e.target);
                o.calculator.formSubmit($form);
            }).on('success.field.bv', function(e, data) {
                data.bv.disableSubmitButtons(!(data.bv.isValidField('country') && data.bv.isValid()));
            });
	        $("#basic-calc")
                .find('[name="country"]')
                    .select2({
                        formatNoMatches: function (term) {
                            return "Oh snap, we don't ship there";
                        },
                        matcher: function(term, text) {
                            if (text.toUpperCase().indexOf(term.toUpperCase()) == 0) {
                                return true;
                            }
                            return false;
                        }
                    })
                    // Revalidate the color when it is changed
                    .change(function(e) {
                        var $basic_calc = $('#basic-calc');
                        $basic_calc.bootstrapValidator('revalidateField', 'country');
                        $basic_calc.bootstrapValidator('revalidateField', 'postcode');
                    })
                    .end()
                .bootstrapValidator({
                    container: '#calculator-messages',
                    excluded: [':disabled', "#id_city"],
                    verbose: false,
                    fields: {
                        country: {
                            validators: {
                                callback: {
                                    message: 'The destination country is required',
                                    callback: function(value, validator, $field) {
                                        return value.length > 0;
                                    }
                                }
                            }
                        },
                        postcode: {
                            validators: {
                                callback: {
                                    callback: function(value, validator, $field) {
                                        var country_code = validator.getFieldElements('country').val(),
                                            country_regex = POSTOCDES_REGEX[country_code];

                                        if(value !== '' && country_code !== '') {
                                            return true;
                                        }else if(value === '' && country_code !== '') {
                                            if(country_regex === undefined) {
                                                return true;
                                            }else {
                                                return {
                                                    valid: false,
                                                    message: 'The postal code is required'
                                                }
                                            }
                                        }
                                        else {
                                            return true;
                                        }
                                    }
                                }
                            }
                        },
                        value: {
                            validators: {
                                notEmpty: {
                                    message: 'The value field is required'
                                },
                                between: {
                                    min: 1,
                                    max: 10000,
                                    message: 'Value must be between $1 and $10000'
                                },
                                regexp: {
                                    regexp: /^\d{1,4}(\.\d{0,2})?$/,
                                    message: 'Ensure that there are no more than 2 digits after the decimal point and no more than 4 before'
                                }
                            }
                        },
                        weight: {
                            validators: {
                                notEmpty: {
                                    message: 'The weight field is required'
                                },
                                numeric: {
                                    message: 'Please enter a number'
                                },
                                greaterThan: {
                                    value: 0.1,
                                    message: 'Ensure this value is greater than or equal to 0.1.'
                                },
                                regexp: {
                                    regexp: /^\d{1,3}(\.\d{0,2})?$/,
                                    message: 'Ensure that there are no more than 2 digits after the decimal point and no more than 3 before'
                                }
                            }
                        },
                        height: {
                            validators: {
                                notEmpty: {
                                    message: 'The height field is required'
                                },
                                numeric: {
                                    message: 'Please enter a number'
                                },
                                greaterThan: {
                                    value: 0.1,
                                    message: 'Ensure this value is greater than or equal to 0.1.'
                                },
                                regexp: {
                                    regexp: /^\d{1,3}(\.\d{0,2})?$/,
                                    message: 'Ensure that there are no more than 2 digits after the decimal point and no more than 3 before'
                                }
                            }
                        },
                        width: {
                            validators: {
                                notEmpty: {
                                    message: 'The width field is required'
                                },
                                numeric: {
                                    message: 'Please enter a number'
                                },
                                greaterThan: {
                                    value: 0.1,
                                    message: 'Ensure this value is greater than or equal to 0.1.'
                                },
                                regexp: {
                                    regexp: /^\d{1,3}(\.\d{0,2})?$/,
                                    message: 'Ensure that there are no more than 2 digits after the decimal point and no more than 3 before'
                                }
                            }
                        },
                        length: {
                            validators: {
                                notEmpty: {
                                    message: 'The length field is required'
                                },
                                numeric: {
                                    message: 'Please enter a number'
                                },
                                greaterThan: {
                                    value: 0.1,
                                    message: 'Ensure this value is greater than or equal to 0.1.'
                                },
                                regexp: {
                                    regexp: /^\d{1,3}(\.\d{0,2})?$/,
                                    message: 'Ensure that there are no more than 2 digits after the decimal point and no more than 3 before'
                                }
                            }
                        }
                    }
	        }).on('success.form.bv', function(e) {
                // Prevent form submission
                e.preventDefault();
                // Get the form instance
                var $form = $(e.target);
                o.calculator.formSubmit($form);
            }).on('success.field.bv', function(e, data) {
                data.bv.disableSubmitButtons(!(data.bv.isValidField('country') && data.bv.isValid()));
            });
        }
    };

    o.spinner = {
        startSpinner: function() {
            var $shipping_method_loading = $('.shipping-methods-loading'),
            $shipping_methods_spinner = $('.spin');

            $shipping_method_loading.show();
            $shipping_methods_spinner.spin('medium');
        },
        stopSpinner: function() {
            $('.spin').spin(false);
            $('.shipping-methods-loading').hide();
        },
        initSpinner: function() {
            (function(factory) {
              if (typeof exports == 'object') {
                // CommonJS
                factory(require('jquery'), require('spin'))
              }
              else if (typeof define == 'function' && define.amd) {
                // AMD, register as anonymous module
                define(['jquery', 'spin'], factory)
              }
              else {
                // Browser globals
                if (!window.Spinner) throw new Error('Spin.js not present');
                factory(window.jQuery, window.Spinner)
              }

            }(function($, Spinner) {

              $.fn.spin = function(opts, color) {

                return this.each(function() {
                  var $this = $(this),
                    data = $this.data();

                  if (data.spinner) {
                    data.spinner.stop();
                    delete data.spinner;
                  }
                  if (opts !== false) {
                    opts = $.extend(
                      { color: color || $this.css('color') },
                      $.fn.spin.presets[opts] || opts
                    );
                    data.spinner = new Spinner(opts).spin(this)
                  }
                })
              };

              $.fn.spin.presets = {
                tiny: { lines: 8, length: 2, width: 2, radius: 3, top: '0'},
                small: { lines: 10, length: 4, width: 3, radius: 5, top: '50%', left: '8%' },
                medium: { lines: 10, length: 6, width: 3, radius: 5, top: '28%', left: '15%' },
                large: { lines: 10, length: 8, width: 4, radius: 8, top: '28%', left: '5%' }
              }
            }));
        }
    };

    o.shipping_methods = {
        init: function(){
            var $page_inner = $('.page_inner');

            $page_inner.on('click', '.shipment-item', function() {
                var $this = $(this),
                    method_code = $this.data('method-code');
                //remove active class from all items
                $('.shipment-item').removeClass('active');
                $this.addClass('active');
                //set selected method code
                $('input[name="method_code"]').val(method_code);
                if(method_code == 'FirstClassPackageInternationalService') {
                    $('#first-class-notice').show();
                    $('#insurance-required').prop('checked', true);
                    $('input[name="insurance"]').val('yes');
                    $('.switch-animate').removeClass('switch-off').addClass('switch-on');
                }
                else {
                    $('#first-class-notice').hide();
                    //set no insurance needed
                    $('#insurance-required').prop('checked', false);
                    $('input[name="insurance"]').val('no');
                    $('.switch-animate').removeClass('switch-on').addClass('switch-off');
                }
                //open the insurance modal
                $('#insuranceModal').modal('toggle');
            });
            $page_inner.on('click', '#insurance-action', function() {
                //set if insurance is needed or not
                $('input[name="insurance"]').val($('#insurance-required').prop('checked') ? 'yes' : 'no');
                //move to next step
                $("#shipment-confirmed").click();
            });
            $page_inner.on('shown.bs.modal', '#insuranceModal', function() {
                //enable the move to next step button
                $('#shipment-confirmed').removeAttr('disabled');
            });
            //start the background worker
            o.spinner.initSpinner();
            o.shipping_methods.runShippingMethodsTask();
        },
        runShippingMethodsTask: function() {
            $.ajax({
                type: 'GET',
                url: '.',
                beforeSend: function() {
                    $('#messages').html('');
                    //start the spinner
                    o.spinner.startSpinner();
                },
                success: function(data) {
                    if(data.redirect){
                        window.location.replace(data.redirect);
                    }
                    else{
                        if(data.new_results){
                            o.task.handle_celery_task_status(data, data.task_id, data.status_url,
                                o.task.handleShippingMethodsResults,
                                o.task.handleShippingMethodsResultsFailure);
                        }
                        else{
                            //In case we don't need to retrieve new methods, wait for 1 second before showing the results
                            setTimeout(function (){
                                //stop the spinner and hide it
                                o.spinner.stopSpinner();
                                o.task.handleShippingMethodsResults(data);
                            }, 1000);
                        }
                        o.initSwitch();
                    }
                },
                dataType:'json'
                            });
                        }
                    };

    o.thank_you = {
        init: function() {
            var $page_inner = $('.page_inner');

            analytics.ready(function() {
                //track clicks on the get shipping credit link
                analytics.trackLink($('#shipping-credit'), 'Clicked Shipping Credit Link');
            });
            //open the order processing modal
            $('#orderProcessingModal').modal({
                backdrop: 'static',
                keyboard: false,
                show: true
            });
            $page_inner.on('hide.bs.modal', '#orderProcessingModal', function(e) {
                $('.cover').removeClass('blur-in').addClass('blur-out');
            });
            o.spinner.initSpinner();
            $('.loading').spin('medium');
            o.thank_you.runOrderProcessingTask();
        },
        runOrderProcessingTask: function() {
            $.ajax({
                type: 'GET',
                url: '.',
                success: function(data) {
                    if(data.body_html) {
                        var $orderProcessingModalBody = $('#orderProcessingModalBody');

                         //stop the spinner and hide it
                        $('.loading').spin(false);
                        $orderProcessingModalBody.html(data.body_html);
                        if(data.footer_html) {
                            $orderProcessingModalBody.after(data.footer_html);
                        }
                        if(data.redirect_url) {
                            setTimeout(function() {
                                window.location = data.redirect_url;
                            }, 10000);
                        }
                    }
                    else {
                        //poll server every 2 seconds
                        setTimeout(o.thank_you.runOrderProcessingTask, 2000);
                    }
                },
                dataType:'json'
            });
        }
    };

    o.battery_status = function(form_selector) {
        var $page_inner = $('.page_inner');
        $page_inner.on('click', '#lithiumBatteryModalFooter button', function() {
            var data = {
                'status': $(this).data('battery-status'),
                'request_type': 'battery-status'
            };
            $.ajax({
                type: 'POST',
                url: '.',
                data : data,
                success: function(res) {
                    if(res == 'SUCCESS')
                        $('#lithiumBatteryModal').modal('hide');
                    else
                        $('#lithiumBatteryModalBody').html("<p>Something went wrong, please try again later</p>")
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    $('#lithiumBatteryModalBody').html("<p>Something went wrong, please try again later</p>")
                }
            });
        });
        $page_inner.on('submit', function(e) {
            var battery_modal = $('#lithiumBatteryModal');
            if(battery_modal.length) {
                e.preventDefault();
                battery_modal.modal({
                    backdrop: 'static',
                    keyboard: false,
                    show: true
                });
            }
        });
        $page_inner.on('hide.bs.modal', '#lithiumBatteryModal', function() {
            $('#lithiumBatteryModal').remove();
            $(form_selector).submit();
        });
    };

    o.custom_form = {
        init: function () {
            var $page_inner = $('.page_inner');
            $("input[id^='id_content_desc']").each(function(index){
                o.custom_form.item_processing($(this), index, 2, true);
            });
            $("input[id^='id_content_desc']:visible").each(function(index){
                o.custom_form.item_processing($(this), index, 1, false);
            });
            $("input[id^='id_content_value']:visible").each(function(){
                var $this = $(this);

                if(!$this.closest('.form-group').hasClass('has-error') &&
                    parseInt(this.value, 10) === 0){
                    $this.val('');
                    $this.removeAttr('readonly');
                    $this.closest('.form-group').addClass('has-error');
                }
            });
            $page_inner.on('click', '#extra_customs_item', function(e) {
                e.preventDefault();
                $('.customs-item-container').filter(':hidden:first').show();
            });
            o.battery_status('#customs_declaration_form');
        },
        item_processing: function($desc_elem, cur_index, start_index, is_hide){
            var $quantity_elem = $('#id_content_quantity' + cur_index),
                $value_elem = $('#id_content_value' + cur_index),
                desc_val = $desc_elem.val(),
                quantity_val = $quantity_elem.val(),
                value_val = $value_elem.val();
            if(cur_index >= start_index){
                if(is_hide){
                    if(!desc_val && !quantity_val && !value_val){
                        $desc_elem.closest('.customs-item-container').hide();
                    }
                }
                else{
                    if(!(!desc_val && !quantity_val && !value_val)){
                        if(!desc_val){
                            $desc_elem.closest('.form-group').addClass('has-error');
                        }
                        if(!quantity_val){
                            $quantity_elem.closest('.form-group').addClass('has-error');
                        }
                        if(!value_val){
                            $value_elem.closest('.form-group').addClass('has-error');
                        }
                    }
                }
            }
        }
    };

    o.notifications = {
        init: function() {
            var $page_inner = $('.page_inner');

            $page_inner.on('click', '.select-all-btn', function() {
                $(this).closest('.notifications-top').
                    find(":checkbox[name='selected_notification']").click();
            });
            $page_inner.on('click', '#deleteNotifications', function() {
                $(this).closest('.notifications-top').
                    find("form").submit();
            })
        }
    };

    o.referrals = {
        init: function () {
            var $page_inner = $('.page_inner'),
                clipboard = new Clipboard('#copy-referral-link');

            o.spinner.initSpinner();
            analytics.ready(function() {
                //track clicks on the share on Twitter button
                analytics.trackLink($('#twitter-share'), 'Clicked Share Link', {
                    linkType: 'Twitter'
                });
            });
            $('#invite-google-contacts').click(function() {
                o.referrals.google_auth($(this).data('load-url'));
            });
            $('[data-show-contacts="true"]').each(function() {
                o.referrals.google_contacts($(this).data('load-url'));
            });
            $page_inner.on('click', '#friendsModalSubmit', function(e) {
                var $email_tags = $('#email-tags'),
                    tags = $email_tags.data('tags');
                $.ajax({
                    type: 'POST',
                    url: $email_tags.data('url'),
                    data : {'email_tags': JSON.stringify(tags)},
                    success: function(data) {
                        window.location = data.redirect_url;
                    }
                });
            });
            $page_inner.on('show.bs.modal', '#friendsModal', function(e) {
                var width = '540px';

                if($(window).width() <= 767) {
                    width = '300px'
                }
                $('#email-tags').tagThis({
                    noDuplicates: true,
                    email: true,
                    defaultText: '',
                    createTagWith: ' ',
                    height : '230px',
                    width : width,
                    callbacks: {
                        afterAddTag: o.referrals.add_email_tag,
                        afterRemoveTag: o.referrals.remove_email_tag
                    }
                });
            });
            $page_inner.on('hide.bs.modal', '#friendsModal', '#googleContactsModal', function(e) {
                $('#google-contacts-potential-credit').text('0');
                $('#friends-potential-credit').text('0');
                $('#google-contacts-invites').text('0').parent('button').prop("disabled", true);
                $('#friends-invites').text('0').parent('button').prop("disabled", true);
            });
            $page_inner.on('click', '.gcontacts-item', function(e) {
                var $this = $(this),
                    contact_input = $this.find('input');
                if(e.target.checked || (e.target.checked === undefined && !contact_input.is(":checked"))) {
                    $this.addClass('selected');
                    contact_input.prop('checked', true);
                    o.referrals.credit_added($('#google-contacts-potential-credit'), $('#google-contacts-invites'));
                }
                else {
                    $this.removeClass('selected');
                    contact_input.prop('checked', false);
                    o.referrals.credit_removed($('#google-contacts-potential-credit'), $('#google-contacts-invites'));
                }
            });
            clipboard.on('success', function(e) {
                $('#copy-referral-link').select();
                $('#copy-referral-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#copy-referral-link').unselect();
                $('#copy-referral-action').text('Not Copied').show().fadeOut(1000);
            });
        },
        add_email_tag: function() {
            o.referrals.credit_added($('#friends-potential-credit'), $('#friends-invites'));
        },
        remove_email_tag: function() {
            o.referrals.credit_removed($('#friends-potential-credit'), $('#friends-invites'));
        },
        google_auth: function(url) {
            $.ajax({
                type: 'POST',
                url: url,
                data: {'action': 'google-auth'},
                success: function(data) {
                    window.location = data.redirect_url;
                },
                dataType:'json'
            });
        },
        google_contacts: function(url) {
            //only issue the ajax call if we haven't populated the contacts list already
            if($('#google-contacts').is(':empty')) {
                $.ajax({
                    type: 'GET',
                    url: url,
                    beforeSend: function() {
                        $('.loading').spin('medium');
                        $('#googleContactsModal').modal('toggle');
                    },
                    success: function(data) {
                        if(data.redirect_url) {
                            window.location = data.redirect_url;
                        }
                        else {
                            o.task.handle_celery_task_status(data, data.task_id, data.status_url,
                                o.referrals.google_contacts_success_cb,
                                o.referrals.google_contacts_failure_cb);
                        }
                    },
                    dataType:'json'
                });
            }
            else {
                $('#googleContactsModal').modal('toggle');
            }
        },
        google_contacts_success_cb: function(data) {
            if(data.redirect_url) {
                window.location = data.redirect_url;
            }
            else {
                $('.loading').spin(false);
                $('#google-contacts').html(data.contacts_html);
                $('#search-google-contacts').hideseek()
                    .on("_after", function() {
                    $('input[name="google_contact"]:checked').parent('.gcontacts-item').addClass('selected');
                });
            }
        },
        google_contacts_failure_cb: function(data) {
            $('.loading').spin(false);
            $('#messages').html('');
            o.messages.addMessages(data.messages);
        },
        credit_added: function($potential_credit, $invite_count) {
            var total_credit  = parseInt($potential_credit.text()),
                total_invites = parseInt($invite_count.text());

            total_credit += 5;
            $potential_credit.text(total_credit);
            total_invites += 1;
            $invite_count.text(total_invites);
            $invite_count.parent('button').prop("disabled", false);
        },
        credit_removed: function($potential_credit, $invite_count) {
            var total_credit  = parseInt($potential_credit.text()),
                total_invites = parseInt($invite_count.text());

            if(total_credit > 0) {
                total_credit -= 5;
            }
            $potential_credit.text(total_credit);
            if(total_invites > 0) {
                total_invites -= 1;
            }
            if(total_invites == 0) {
                $invite_count.parent('button').prop("disabled", true);
            }
            $invite_count.text(total_invites);
        }
    };

    o.checkout = {
        init: function() {
            if (typeof(Storage) !== "undefined") {
                analytics.ready(function() {
                    var clientID = sessionStorage.clientID;

                    if(!clientID) {
                        o.checkout.getClientID(function(clientID) {
                            if(clientID) {
                                sessionStorage.clientID = clientID;
                            }
                        });
                    }
                });
            }
        },
        getClientID: function(cb) {
            ga(function(tracker) {
                var clientID = tracker.get('clientId');
                cb(clientID);
            });
        }
    };

    o.profile = {
        init: function () {
            var name_clipboard = new Clipboard('#address-name'),
                address1_clipboard = new Clipboard('#address-line1'),
                address2_clipboard = new Clipboard('#address-line2'),
                city_clipboard = new Clipboard('#address-city'),
                state_clipboard = new Clipboard('#address-state'),
                zip_clipboard = new Clipboard('#address-zip'),
                country_clipboard = new Clipboard('#address-country'),
                phone_clipboard = new Clipboard('#address-phone'),
                $shipping_regs_modal = $('#shippingRegulationsModal'),
                $page_inner = $('.page_inner');

            o.profile.initCounters();
            $('.drop-button').click(function() {
                $(this).tooltip('toggle');
		        $(this).next('ul').toggle();
	        }).hover(function() {
                $(this).tooltip({
                    placement: 'bottom',
                    title: 'Notifications'
                }).tooltip('show');
            });
            $('a[role="tab"]').click(function() {
                o.profile.initCounters();
            });
            $('.form-group.invisible:lt(3)').removeClass('invisible');
            $('.btn-more-services').click(function() {
                $(this).find('i').toggleClass('fa-caret-down').toggleClass('fa-caret-up');
                $('.panel-body .form-group.invisible').toggleClass('active');
                if (!$(this).hasClass('active')) {
                    $("html, body").animate({ scrollTop: $('.extra-services-panel').offset().top }, "slow");
                    return false;
                }
            });
            $('.dropdown-menu li, .dropdown-menu li').click(function(e) {
                e.stopPropagation();
            });
            $('#control-panel-tour').click(function() {
                o.profile.initTour();
            });
            $('#shipping-regs').click(function() {
                window.open("/support/faq/shipping/", "targetWindow", "toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes,left=300,width=1400,height=1000");
            });
            $('#prohbited-items-list').click(function() {
                window.open("/support/faq/shipping/#shipping-q2", "targetWindow", "toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes,left=300,width=1400,height=1000");
            });
            name_clipboard.on('success', function(e) {
                $('#address-name').select();
                $('#address-name-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-name').unselect();
                $('#address-name-action').text('Not Copied').show().fadeOut(1000);
            });
            address1_clipboard.on('success', function(e) {
                $('#address-line1').select();
                $('#address-line1-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-line1').unselect();
                $('#address-line1-action').text('Not Copied').show().fadeOut(1000);
            });
            address2_clipboard.on('success', function(e) {
                $('#address-line2').select();
                $('#address-line2-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-line2').unselect();
                $('#address-line2-action').text('Not Copied').show().fadeOut(1000);
            });
            city_clipboard.on('success', function(e) {
                $('#address-city').select();
                $('#address-city-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-city').unselect();
                $('#address-city-action').text('Not Copied').show().fadeOut(1000);
            });
            state_clipboard.on('success', function(e) {
                $('#address-state').select();
                $('#address-state-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-state').unselect();
                $('#address-state-action').text('Not Copied').show().fadeOut(1000);
            });
            zip_clipboard.on('success', function(e) {
                $('#address-zip').select();
                $('#address-zip-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-zip').unselect();
                $('#address-zip-action').text('Not Copied').show().fadeOut(1000);
            });
            country_clipboard.on('success', function(e) {
                $('#address-country').select();
                $('#address-country-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-country').unselect();
                $('#address-country-action').text('Not Copied').show().fadeOut(1000);
            });
            phone_clipboard.on('success', function(e) {
                $('#address-phone').select();
                $('#address-phone-action').text('Copied').show().fadeOut(1000);
            }).on('error', function(e) {
                $('#address-phone').unselect();
                $('#address-phone-action').text('Not Copied').show().fadeOut(1000);
            });
            $("#welcome-video").on('click', function() {
                $("#onboardingModal").modal('show');
            });
            var package_consolidation = o.getUrlVars()["package-consolidation"];
            var extra_services = o.getUrlVars()["extra-services"];
            if(package_consolidation == 'true')
                $("#packageConsolidationModal").modal('show');
            if(extra_services == 'true')
                $("#extraServicesModal").modal('show');
            if($shipping_regs_modal.length) {
                $shipping_regs_modal.modal('show');
                $page_inner.on('hidden.bs.modal', '#shippingRegulationsModal', function (e) {
                    setTimeout(function () {
                        o.profile.initTour();
                    }, 100);
                });
            }
            if (typeof(Storage) !== "undefined") {
                var club_modal = $('#exclusiveClubModal');
                if(club_modal.length) {
                    if(localStorage.show_club_modal !== 'true') {
                        localStorage.show_club_modal = 'true';
                        club_modal.modal('show');
                    }
                }
            }
        },
        initCounters: function() {
            var $incomingCounter = $('#incoming-counter'),
                incomingCount = $incomingCounter.data('count'),
                $ConsolidationCounter = $('#consolidation-counter'),
                ConsolidationCount = $ConsolidationCounter.data('count');

            $incomingCounter.circleProgress({
                value: incomingCount / 20,
                size: 100,
                fill: {
                    color: "#ff6c60"
                }
            });
            $ConsolidationCounter.circleProgress({
                value: ConsolidationCount / 20,
                size: 100,
                fill: {
                    color: "#ff6c60"
                }
            });
        },
        initTour: function() {
            if (!$('#control-panel-tour').length)
                return;

            // Instance the tour
            var tour = new Tour({
                backdrop: true,
                storage: false,
                onStart: function (tour) {
                    //post back to server to audit stats on the number of users who completed the tour
                    $.post("/accounts/welcome-tour/", {end_step: 0});
                },
                onEnd: function (tour) {
                    //post back to server to audit stats on the number of users who completed the tour
                    $.post("/accounts/welcome-tour/", {end_step: tour.getCurrentStep()});
                },
                steps: [
                    {
                        element: "#usendhome-address-tour",
                        title: "Delivering Orders to Us",
                        content: '<h5 style="font-weight: 600">This is a quick tour don\'t worry :)</h5>' +
                                 "<p>Every online shopping spree ends up with an order where a shipping address" +
                                 " must be filled in. This is where USendHome service comes to the rescue.</p>" +
                                 "<p>Use your personal US shipping address listed on your left to deliver your orders to our warehouse.</p>" +
                                 "<p>Don't forget to include your USH number so we could identify your package quickly.</p>"
                    },
                    {
                        element: "#manage-packages-tour",
                        title: "Manage Your Packages",
                        content: "<p>This is where we shine, we've created a user-friendly package management system" +
                                 " that puts you in the driver's seat.</p>" +
                                 "<p>You can order extra services, merge your orders into one shipment, release your packages" +
                                 " for delivery or return them back to the merchant, all in one place.</p>"
                    },
                    {
                        element: "#extra-services-tour",
                        title: "Money Saver for the Planning Ahead",
                        placement: "left",
                        content: "<p><strong>This section can save you a lot of money!</strong></p>" +
                                 "<p>Yes, you heard it right, just select in advance what actions" +
                                 " you would like our operations staff to take on your packages and save money.</p>" +
                                 "<p>This includes consolidated packages as well, order extra services before you " +
                                 "ask us to merge your items and receive 20% off.</p>"
                    },
                    {
                        element: "#referral-program-tour",
                        title: "Give $5, Get $5",
                        placement: "left",
                        content: "<p>We are sure, you must have friends that would want to use a service like USendHome. Invite your friends to USendHome and:</p>" +
                                 "<ul><li><strong>Your friend gets a FREE US Forwarding Address and earn $5 in instant shipping credit.</strong></li>" +
                                 "<li><strong>You earn $5 in shipping credit when your friend forwards their first package, simple as that.</strong></li></ul>"
                    },
                    {
                        element: "#address-book-tour",
                        title: "Manage Your Addresses",
                        content: "<p>Speed up the checkout process by creating an address book.</p>" +
                                 "<p>Wait, what would you say if we told you that we can handle it for you.</p>" +
                                 "<p>Each new shipping address, captured during the checkout process " +
                                 "is automatically added in to your address book so you will not have to enter it again!</p>"
                    },
                    {
                        element: "#account-tour",
                        title: "Manage Your Account",
                        placement: "left",
                        content: "<p>While you wait for your packages to come in, you may find this section handy.</p>" +
                                 "<p>In this section you can invite friends to USendHome, view latest notifications, " +
                                 "file insurance claim and most importantly, you can enable" +
                                 " the automatic package tracking system to keep an eye on your items in transit.</p>"
                    },
                    {
                        element: "#order-history-tour",
                        title: "Mange Your Orders",
                        content: "<p>Keep track of your orders, see what orders have been shipped and " +
                                 "get the latest shipping information from the shipping carrier website.</p>"
                    }
                ]
            });

            // Initialize the tour
            tour.init();

            // Start the tour
            tour.start();
        }
    };

    o.packages = {
        init: function() {
            var $page_inner = $('.page_inner');

            $page_inner.on('click', '.btn-more-services', function(e) {
                var $this = $(this);
                $this.find('i').toggleClass('fa-caret-down').toggleClass('fa-caret-up');
                $this.closest('.modal-content').find('.form-group.invisible').toggleClass('active');
            });
            $page_inner.on('show.bs.modal', '.modal-cp', function(e) {
                var $this = $(this),
                    $moreservices = $this.find('.btn-more-services');

                $this.find('.form-group').addClass('invisible');
                $this.find('.form-group.invisible:lt(3)').removeClass('invisible');
                //hide show more service button if no invisible input left
                if (!$this.find('.form-group.invisible').length) {
                    $moreservices.hide();
                }
                else {
                    $moreservices.find('i').removeClass('fa-caret-down').
                        removeClass('fa-caret-up').addClass('fa-caret-down');
                }
            });
            $("#firstPackageModal").modal('show');
        },
        initProductImages: function() {
            $("a.fancybox").fancybox({
                padding: 0,
                nextEffect: 'none',
                prevEffect: 'none'
            });
        }
    };

    o.faq = {
        init: function() {
            $('.drop-nav ul li a').click(function() {
                $('.drop-nav ul li a').removeClass('active');
                $(this).addClass('active');
            });

            $('.faq-nav > ul > li > span').click(function() {
                var $this = $(this),
                    activeFaq = $this.attr('data-faq'),
                    $activeFaqContent = $('.faq-content.active'),
                    parentActive = $this.parent().hasClass('active');

                $('.faq-nav > ul > li > span').find('i:nth-child(2)').
                    removeClass('fa-caret-up').addClass('fa-caret-down');
                $('.faq-nav ul li').removeClass('active');
                if (!parentActive) {
                    $this.parent().addClass('active');
                    $this.find('i:nth-child(2)').removeClass('fa-caret-down').addClass('fa-caret-up');
                }
                else {
                    $activeFaqContent.removeClass('active');
                    $("#" + activeFaq).addClass("active");
                }
                $('html, body').animate({scrollTop:$activeFaqContent.position().top - 100}, 'fast');
            });

            $(".btn-back-top").click(function() {
                $("html, body").animate({ scrollTop: 0 }, "slow");
                return false;
            });

            $(window).scroll(function() {
                if ($(window).scrollTop() >= 400) {
                    $('.btn-back-top').addClass('active');
                    $('.btn-contact-us').addClass('active');
                } else {
                    $('.btn-back-top').removeClass('active');
                    $('.btn-contact-us').removeClass('active');
                }
            });
        }
    };

    o.voucher = {
        init: function() {
            var $page_inner = $('.page_inner');

            $page_inner.on('click', '#voucher_form_link a', function(event) {
                o.voucher.showVoucherForm();
            });
            $page_inner.on('click', '#voucher_form_cancel', function(event) {
                o.voucher.hideVoucherForm();
                event.preventDefault();
            });
            if (window.location.hash == '#voucher') {
                o.voucher.showVoucherForm();
            }
        },
        showVoucherForm: function() {
            $('#voucher_form_container').show();
            $('#voucher_form_link').hide();
        },
        hideVoucherForm: function() {
            $('#voucher_form_container').hide();
            $('#voucher_form_link').show();
        }
    };

    o.fileUpload = {
        init: function() {
            var filesList = [],
                paramNames = [],
                $page_inner = $('.page_inner'),
                $form = $('form');

            o.fileUpload.initFileUpload($form, filesList, paramNames);
            $page_inner.on('click', '.btn-start-upload', function(e){
                var $form = $('form');
                e.preventDefault();
                if (filesList.length) {
                    $form.fileupload('send', {files: filesList, paramName: paramNames, formData: $form.serializeArray()});
                    $("html, body").animate({ scrollTop: $('.upload-top').offset().top - 150 }, "slow");
                }
                else {
                    $form.submit();
                }
            });
        },
        error: function(msg) { o.fileUpload.addMessage('danger', msg, '<i class="fa fa-exclamation-circle"></i>'); },
        addMessage: function(tag, msg, icon) {
            var msgHTML = '<div class="alert fade in alert-' + tag + '">' +
                '<a href="#" class="close" data-dismiss="alert">&times;</a>'  + icon +
                ' ' + msg + '</div>';
            $('form .js-errors').html($(msgHTML));
        },
        initFileUpload: function($form, filesList, paramNames) {
            $form.fileupload({
                autoUpload: false,
                fileInput: $("input:file"),
                add: function (e, data) {
                    var uploadFile = data.files[0];

                    $('form .js-errors').html('');
                    if (uploadFile.size > 5000000) { // 5mb
                        o.fileUpload.error('Max file size is 5 MB');
                    }
                    else if (!(/\.(jpg|jpeg|png|pdf)$/i).test(uploadFile.name)) {
                        o.fileUpload.error('Only JPG, JPEG, PNG and PDF file formats are supported');
                    }
                    else if (!(/^[A-Za-z0-9_.-]*$/).test(uploadFile.name)) {
                        o.messages.error('File name must include English characters, (_-) or numbers only');
                    }
                    else {
                        filesList.push(data.files[0]);
                        paramNames.push(e.delegatedEvent.target.name);
                        $('input[name='+e.delegatedEvent.target.name+']').prev('span').text(uploadFile.name);
                    }
                },
                dataType: 'json',
                progressall: function (e, data) {
                    var progress = parseInt(data.loaded / data.total * 100, 10);
                    $('#progress .progress-bar').css(
                        'width',
                        progress + '%'
                    );
                    $('#progress').css('display', 'block');
                },
                done: function (e, data) {
                    if (data.result.redirect_url) {
                        window.location = data.result.redirect_url;
                    }
                    else {
                        //replace form html with invalid form html
                        $('form').html(data.result.content_html);
                        //hide progress bar
                        $('#progress').css('display', 'none');
                        //register selcet2
                        o.register_select2();
                        filesList.length = 0;
                        paramNames.length = 0;
                        o.fileUpload.initFileUpload($form, filesList, paramNames);
                    }
                },
                fail: function (e, data) {
                    //$.each(data.messages, function (index, error) {
                    //    o.fileUpload.error(error);
                    //});
                    //show general error as we don't want to show technical error message
                    o.fileUpload.error("Something went wrong, please try again later.");
                    //hide progress bar
                    $('#progress').css('display', 'none');
                    filesList.length = 0;
                    paramNames.length = 0;
                    o.fileUpload.initFileUpload($form, filesList, paramNames);
                    $('.btn-start-upload').button('reset');
                }
            }).prop('disabled', !$.support.fileInput)
                .parent().addClass($.support.fileInput ? undefined : 'disabled');
        }
    };

    o.return_to_store_gw = {
        init: function () {
            $('#fileupload').fileupload({
                formData:[
                    {name: 'prepaid_label_submit'},
                    {
                        name: 'csrfmiddlewaretoken',
                        value: $('#return-label-form').find('input[name="csrfmiddlewaretoken"]').val()
                    }
                ],
                url: window.location.href,
                add: function (e, data) {
                    var uploadFile = data.files[0],
                        $messages = $('#messages');

                    $('#payment-confirm').attr('disabled', true);
                    $messages.html('');

                    if (uploadFile.size > 5000000) { // 5mb
                        o.messages.error('Max file size is 5 MB');
                    }
                    else if (!(/\.(jpg|jpeg|png|pdf)$/i).test(uploadFile.name)) {
                        o.messages.error('Only JPG, JPEG, PNG or PDF file type supported');
                    }
                    else if (!(/^[A-Za-z0-9._-]*$/).test(uploadFile.name)) {
                        o.messages.error('File name must include English characters, (-_) or numbers only');
                    }
                    else {
                        data.submit();
                    }
                },
                dataType: 'json',
                progressall: function (e, data) {
                    var progress = parseInt(data.loaded / data.total * 100, 10);
                    $('#progress .progress-bar').css(
                        'width',
                        progress + '%'
                    );
                    $('#progress').css('display', 'block');
                },
                done: function (e, data) {
                    //wait 1 second before showing the success message and enabling the next step button
                    setTimeout(function() {
                        o.return_to_store_gw.processResponse(data)
                    }, 1000);
                },
                fail: function (e, data) {
                    //$.each(data.messages, function (index, error) {
                    //    o.messages.error(error);
                    //});
                    o.messages.error("Something went wrong, please try again later.");
                    //hide progress bar
                    $('#progress').css('display', 'none');
                }
            }).prop('disabled', !$.support.fileInput)
                .parent().addClass($.support.fileInput ? undefined : 'disabled');
        },
        processResponse: function(data) {
            if(data.result.is_valid) {
                $('#payment-confirm').removeAttr('disabled');
            }
            o.messages.addMessages(data.result.messages);
        }
    };

    o.payment_method = {
        init: function() {
            var clientID = null;

            $('.btn-paypal').on('click', function() {
                var $this = $(this);
                $('.btn-paypal').each(function () {
                    $(this).attr('disabled', true);
                });
                $this.trigger('blur');
                $this.button('loading');
                $this.closest('form').submit();
            });

            try {
                clientID = sessionStorage.clientID;
            } catch(err) {}

            if(clientID) {
                o.payment_method.setClientID(clientID);
            }
            else {
                analytics.ready(function() {
                    o.checkout.getClientID(function(clientID) {
                        if(clientID) {
                            o.payment_method.setClientID(clientID);
                        }
                    });
                });
            }

            //open the customs duties modal
            var customs_modal = $('#customsDutiesModal'),
                storage_available = typeof(Storage) !== "undefined";

            if(customs_modal.length) {
                if(!storage_available || localStorage.show_customs_modal !== 'true') {
                    if(storage_available) {
                        localStorage.show_customs_modal = 'true';
                    }
                    customs_modal.modal({
                        backdrop: 'static',
                        keyboard: false,
                        show: true
                    });
                }
            }
        },
        setClientID: function(clientID) {
            $('input[name="client-id"]').each(function () {
                $(this).val(clientID);
            });
        }
    };

    return o;

})(usendhome || {}, jQuery);


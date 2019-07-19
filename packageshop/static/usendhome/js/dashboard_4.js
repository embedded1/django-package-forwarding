var usendhome = (function(o, $) {
    o.getCsrfToken = function() {
        // Extract CSRF token from cookies
        var cookies = document.cookie.split(';');
        var csrf_token = null;
        $.each(cookies, function(index, cookie) {
            cookieParts = $.trim(cookie).split('=');
            if (cookieParts[0] == 'csrftoken') {
                csrfToken = cookieParts[1];
            }
        });
        return csrfToken;
    };

    o.messages = {
        addMessage: function(tag, msg) {
            var msgHTML = '<div class="alert fade in alert-' + tag + '">' +
                '<a href="#" class="close" data-dismiss="alert">x</a>'  + msg +
                '</div>';
            $('#messages').append($(msgHTML));
        },
        addMessages: function(data){
            for (var level in data) {
                for (var i=0; i<data[level].length; i++) {
                    o.messages[level](data[level][i]);
                }
            }
        },
        debug: function(msg) { o.messages.addMessage('debug', msg); },
        info: function(msg) { o.messages.addMessage('info', msg); },
        success: function(msg) { o.messages.addMessage('success', msg); },
        warning: function(msg) { o.messages.addMessage('warning', msg); },
        error: function(msg) { o.messages.addMessage('error:', msg); }
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

    o.initModalLoad = function(cb)  {
        var $page_content = $('.page-content');

        $page_content.on('click', '.modalFormSubmit', function(e) {
            $(this).closest('.modal').find('form').submit();
        });

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
             $page_content.off('click', '.modalRemoteLoad');
        }

        $page_content.on('click', '.modalRemoteLoad', function() {
            var $this = $(this),
                load_url = $this.data('load-url'),
                modal_id = '#' + $this.data('modal-name'),
                modal_body_id = modal_id + 'Body';

            $(modal_body_id).load(load_url, function () {
                $(modal_id).on('show.bs.modal', function (e) {
                    o.formAjaxSubmit(modal_body_id +' form', modal_id, cb);
                });
                $(modal_id).modal('toggle');
            });
        });
    };

    o.dashboard = {
        init: function(options){
            $('select').each( function () {
                var $this = $(this),
                    is_readonly = $this.is('[readonly]');
                $this.select2({minimumResultsForSearch: 10});
                //$('.select2-container').css("width", "100%");
                $this.select2("readonly", is_readonly);
            });
            o.initModalLoad();
            $('.page-content').on('click', '.submit_form', function(e) {
                e.preventDefault();
                $(this).parents("form").submit();
            });
            // Disable buttons when they are clicked
            $('.js-disable-on-click').click(function(){$(this).button('loading');});
            $('input.select2').each(function(i, e) {
                var opts = {};
                if($(e).data('ajax-url')) {
                    opts = {
                        'minimumInputLength': 1,
                        'ajax': {
                            'url': $(e).data('ajax-url'),
                            'dataType': 'json',
                            'results': function(data, page) {
                                if((page==1) && !($(e).data('required')=='required')) {
                                    data.results.unshift({'id': '', 'text': '------------'});
                                }
                                return data;
                            },
                            'data': function(term, page) {
                                return {
                                    'q': term,
                                    'page': page
                                };
                            }
                        },
                        'multiple': $(e).data('multiple'),
                        'initSelection': function(e, callback){
                            if($(e).val()) {
                                $.ajax({
                                    'type': 'GET',
                                    'url': $(e).data('ajax-url'),
                                    'data': [{'name': 'initial', 'value': $(e).val()}],
                                    'success': function(data){
                                        if(data.results) {
                                            if($(e).data('multiple')){
                                                callback(data.results);
                                            } else {
                                                callback(data.results[0]);
                                            }
                                        }
                                    },
                                    'dataType': 'json'
                                });
                            }
                        }
                    };
                }
                $(e).select2(opts);
            });
        },
        return_labels: {
            init: function(){
                var $page_content = $('.page-content');
                $page_content.on('click', '#download-return-label', o.dashboard.return_labels.download_return_labels);
            },
            download_return_labels: function(e){
                var $form = $(this).closest('form'),
                    payload = $form.serialize();
                e.preventDefault();
                $.ajax({
                    type: 'POST',
                    url: $form.attr('action'),
                    data: payload,
                    success: function(data) {
                        $('.js-disable-on-click').button('reset');
                        if (data.download_url) {
                            window.location = data.download_url;
                            setTimeout(function () {
                                $('input[type="checkbox"]:checked').each(function() {
                                    var row = $(this).closest('tr');
                                    row.hide('slow', function(){ row.remove(); });
                                });
                            }, 100); // remove selected checkbox elements
                        }
                        $('#messages').children('div').slice(1).remove();
                        for (var level in data.messages) {
                            for (var i=0; i<data.messages[level].length; i++) {
                                o.messages[level](data.messages[level][i]);
                            }
                        }
                    },
                    dataType:'json'
                });
            }
        },
        shipping_labels: {
            init: function(){
                var $page_content = $('.page-content');
                $page_content.on('click', '.print-commercial-invoices', o.dashboard.shipping_labels.print_commercial_invoices);
            },
            print_commercial_invoices: function(e){
                var $this = $(this),
                    $form = $this.closest('form'),
                    csrf =  o.getCsrfToken();

                e.preventDefault();
                $.ajax({
                    type: 'POST',
                    url: $form.attr('action'),
                    data: {
                        'action': 'download-commercial-invoice',
                        'batch_id': $this.data('batch-id'),
                        'csrfmiddlewaretoken': csrf
                    },
                    success: function(data) {
                        if (data.download_url) {
                           o.dashboard.shipping_labels.print_url(data.download_url);
                        }
                    },
                    dataType:'json'
                });
            },
            print_url: function(url) {
                var $printFrame = $('#printFrame');

                $printFrame.attr('src', url);
                $printFrame.load(function() {
                    window.frames["printFrame"].focus();
                    window.frames["printFrame"].print();
                });
            }

        },
        product: {
            init: function(){
                var $page_content = $('.page-content');
                $('.control-group.error > ul.help-block').each(function(){
                   var error_text = $(this).text();
                   if(error_text.indexOf('$2499.99') >= 0){
                       var $p = $(this).closest('.control-group').prev('.control-group'),
                           value_val = $p.find('input').val();
                       if(value_val > 1){
                            $p.addClass('error');
                       }
                   }
                });
               $page_content.on('change', '#id_damaged-owner,#id_returned-owner', function(obj) {
                   var owner_name = obj.added.name;
                   $(this).closest('.well').find('.owner_name > span').text(owner_name);
               });
               $page_content.on('change', '#id_product-details-owner', o.dashboard.product.addPredefinedRequests);
               $page_content.on('change', '#id_predefined_parcels', o.dashboard.product.addPredefinedMasterBoxDimensions);
               $page_content.on('keyup', '#id_last_name', o.dashboard.product.getAdditionalReceiverStatus);
               $page_content.on('change', '#id_repackaging_done_0', function(){
                   var $this = $(this);

                   if($this.is(":checked")) {
                       $('#predefined_parcels').show();
                       //$('#predefined-parcel-alert').show();
                       //Clear previous dimensions
                       $('.tab-content input[type="text"][name^="product-details-attr_"][name!="product-details-attr_weight"]').val("");
                       alert("Don't forget to select the predefined box on package dimensions and weight tab");
                   }
               });
               $page_content.on('change', '#id_repackaging_done_1', function(){
                   if($(this).is(":checked")) {
                       if(!$('#id_repackaging_done_0').is(":checked"))
                       {
                          $('#predefined_parcels').hide();
                          //$('#predefined-parcel-alert').hide();
                       }
                   }
               });
               $page_content.on('change', '#id_product-details-attr_is_envelope_0', function(){
                   //show envelope restrictions modal
                   $('#envelopeRestrictionsModal').modal('show');
               });
               $('.form-inline .select2-container.select2').css('width', '15%').css('display', '');
               $page_content.on('change', '#id_custom_requests_done_0', function(){$('#id_custom_requests_details').closest('.form-group').show();});
               $page_content.on('change', '#id_custom_requests_done_1', function(){$('#id_custom_requests_details').closest('.form-group').hide();});
               //hide custom requests details field
               $('#id_custom_requests_details').closest('.form-group').hide();
               //save envelope restrictions from modal to parent
               $page_content.on('click', '#envelope-restrictions-save', function(){
                    $('#id_product-details-too_rigid').val($('#id_too_rigid').is(":checked"));
                    $('#id_product-details-not_rectangular').val($('#id_not_rectangular').is(":checked"));
                    $('#id_product-details-thickness_variations').val($('#id_thickness_variations').is(":checked"));
               });
               $('#s2id_id_product-details-owner').css('display', '');
               $page_content.on('change', '#id_product-details-is_name_matched_0', function(){$('#additional-receiver').hide();});
               $page_content.on('change', '#id_product-details-is_name_matched_1', function(){$('#additional-receiver').show();});
                if($('#id_product-details-is_contain_prohibited_items_1').is(':checked')) {
                    $('#id_product-details-prohibited_items_msg').closest('.control-group').hide();
                }
               $page_content.on('change', '#id_product-details-is_contain_prohibited_items_0', function(){$('#id_product-details-prohibited_items_msg').closest('.control-group').show();});
               $page_content.on('change', '#id_product-details-is_contain_prohibited_items_1', function(){$('#id_product-details-prohibited_items_msg').closest('.control-group').hide();});
               $page_content.on('input', '#id_product-details-attr_height,' +
                   ' #id_product-details-attr_width,' +
                   ' #id_product-details-attr_length', o.dashboard.product.calculate_girth_and_length);
               o.dashboard.product.calculate_girth_and_length();
            },
            calculate_girth_and_length: function(e) {
                var total, girth;
                girth = ((parseFloat($('#id_product-details-attr_height').val()) || 0) +
                        (parseFloat($('#id_product-details-attr_width').val()) || 0)) * 2;
                total = (parseFloat($('#id_product-details-attr_length').val()) || 0) + girth;
                $("#girth-and-length").text(total.toFixed(2) + ' inch');
                //add message if package needs to be split
                if($('#id_container').val() === 'Multiple boxes' && total > 79.0){
                    alert("Package doesn't meet USPS size condition, please split it to smaller boxes as" +
                    " customer would like to ship via the USPS only.")
                }
            },
            getAdditionalReceiverStatus: function(e) {
                var last_name = $(this).val(),
                    first_name = $('#id_first_name').val(),
                    owner_pk = $('#id_product-details-owner').val(),
                    csrf =  o.getCsrfToken(),
                    payload = 'action=additional_receiver_status' + '&owner_pk=' + owner_pk +
                        '&first_name=' + first_name + '&last_name=' + last_name + '&csrfmiddlewaretoken=' + csrf;
                $.ajax({
                    type: 'POST',
                    url: $(location).attr('href'),
                    data: payload,
                    beforeSend: function() {
                        $('#additional-receiver-status').remove();
                    },
                    success: function(data) {
                        var $receiverID = $('#additional-receiver'),
                            $p = $receiverID.next('p');

                        if(data.status_html){
                            if(!$p.length) {
                                $receiverID.after(data.status_html);
                            }
                        }
                    },
                    dataType:'json'
                });
            },
            addPredefinedRequests: function(obj){
                var id = obj.val;
                if($.isNumeric(id)){
                    var csrf =  o.getCsrfToken(),
                        action = $(this).data('action'),
                        payload = 'action=' + action + '&user_id=' + id + '&csrfmiddlewaretoken=' + csrf;
                    $.ajax({
                        type: 'POST',
                        url: $(location).attr('href'),
                        data: payload,
                        beforeSend: function() {
                            $('#attrs_tab').hide();
                            $('#images_tab').hide();
                            $('#special_requests_tab').hide();
                            $('#customs_form_tab').hide();
                        },
                        success: function(data) {
                            if(data.is_valid){
                                $('#product_additional_intake').html(data.product_special_requests_html);
                                //hide custom requests details field
                                $('#id_custom_requests_details').closest('.form-group').hide();
                                if(data.show_package_dim_and_weight_tab){
                                   $('#attrs_tab').show();
                                }
                                else{
                                    //use placeholder values
                                    $('.tab-content input[type="text"][name^="product-details-attr_"]').val("0.0");
                                    $('#id_product-details-attr_is_envelope_1').prop('checked', true);
                                }
                                if(data.show_images_tab){
                                    $('#images_tab').show();
                                }
                                if(data.show_special_requests_tab){
                                    $('#special_requests_tab').show();
                                }
                                if(data.show_customs_form_tab){
                                    $('#customs_form_tab').show();
                                }
                                if(data.show_package_location_tab){
                                   $('#location_tab').show();
                                }
                                $('.owner_name span').text(data.owner_name);
                                //call oscar init because we changed the html
                                //oscar.dashboard.initWYSIWYG();
                            }
                            $('#messages').html('');
                            o.messages.addMessages(data.messages);
                        },
                        dataType:'json'
                    });
                }
            },
            addPredefinedMasterBoxDimensions: function(e){
                var master_box_name = e.val,
                    csrf =  o.getCsrfToken(),
                    action = $(this).data('action'),
                    payload = 'action=' + action + '&predefined_parcel=' + master_box_name + '&csrfmiddlewaretoken=' + csrf;
                $.ajax({
                    type: 'POST',
                    url: $(location).attr('href'),
                    data: payload,
                    success: function(data) {
                        //add fill package dimensions
                        $('.tab-content input[name="product-details-attr_height"]').val(data.height);
                        $('.tab-content input[name="product-details-attr_length"]').val(data.length);
                        $('.tab-content input[name="product-details-attr_width"]').val(data.width).trigger('change');
                        o.messages.addMessages(data.messages);
                    },
                    dataType:'json'
                });
            }
        },
        orders: {
            init: function() {
                $('button[name="download_selected"]').on('click', function() {
                    $.ajax({
                        type: 'POST',
                        url: '.',
                        data: $('.selected_order').serialize(),
                        dataType:'json'
                    });
                });
            },
            initTable: function() {
                var table = $('table'),
                    input = $('<input type="checkbox" />').css({
                        'margin-right': '5px',
                        'vertical-align': 'top'
                    });
                $('th:first', table).prepend(input);
                $(input).change(function(){
                    $('tr', table).each(function() {
                        $('td:first input', this).prop("checked", $(input).is(':checked'));
                    });
                });
            },
            incompleteDeclaration: function() {
                $('.inc-decl-confirm').click(function(e) {
                    e.preventDefault();
                    var order_id = $(this).data('order-pk');
                    $('#incl_decl_order_id').val(order_id);
                    $('#InclDeclModal').modal('show');
                });

                $('#InclDeclModalSubmit').click(function() {
                    $('#InclDeclForm').submit();
                    $('#InclDeclModal').modal('hide');
                });
            },
            ITNHandling: function() {
                $('.add-itn').click(function(e) {
                    e.preventDefault();
                    var order_id = $(this).data('order-pk');
                    $('#itn_order_id').val(order_id);
                    $('#ITNModal').modal('show');
                });

                $('#ITNModalSubmit').click(function() {
                    $('#ITNForm').submit();
                    $('#ITNModal').modal('hide');
                });
            }
        }
    };

    return o;

})(usendhome || {}, jQuery);